// Review: Vorschläge ansehen, Start/Ende feinjustieren, annehmen oder verwerfen, exportieren, Texte.
import { api } from "../api.js";
import { app, pageTop, refreshState, confirmBox } from "../app.js";
import { h, clear, icon, clock, toast, scoreBadge, select, switchEl, field, copyText, eur, num, STATUS, STATUS_CHIP, engineLabel } from "../ui.js";
import { postDialog } from "./postdialog.js";

const CAP_Y = { pop: 70, box: 72, clean: 76, impact: 66 };

function groupWords(words, tpl) {
  const groups = []; let cur = [];
  const flush = () => { if (cur.length) { groups.push({ words: cur, start: cur[0].s, end: cur[cur.length - 1].e }); cur = []; } };
  for (const w of words) {
    const chars = cur.reduce((n, x) => n + x.w.length + 1, 0) + w.w.length;
    if (cur.length && (cur.length >= tpl.max_words || chars > tpl.max_chars || w.s - cur[cur.length - 1].e > 0.7)) flush();
    cur.push(w);
    if (/[.!?…]$/.test(w.w)) flush();
  }
  flush();
  groups.forEach((g, k) => { const nxt = groups[k + 1]?.start; g.until = nxt != null && nxt - g.end <= 0.6 ? nxt : g.end + 0.35; });
  return groups;
}

export async function render(root, args) {
  const pid = +args[0];
  let project = await api.get(`/api/projects/${pid}`);
  if (project.status === "sample") {
    clear(root, pageTop(project.title), h("div", { class: "panel empty" }, icon("film"), h("b", {}, "Beispielprojekt ohne Video"), "Hier gibt es nichts zu prüfen. Importiere ein eigenes Video unter „Videos“."));
    return {};
  }
  const [tr, campaigns, settings] = await Promise.all([api.get(`/api/projects/${pid}/transcript`), api.get("/api/campaigns"), api.get("/api/settings")]);
  let clips = project.clips;
  let sel = clips.find(c => c.id === +args[1]) || clips.find(c => c.status === "candidate") || clips[0] || null;
  let jobs = app.state.jobs;
  const tplMeta = Object.fromEntries(app.meta.templates.map(t => [t.id, t]));

  const listEl = h("div", { class: "sugg" });
  const editorEl = h("section", { class: "panel hud" });
  const topEl = h("div");
  let ed = null;                 // Zustand des geöffneten Editors (Video, Schleife, Elemente)

  const exportJob = c => jobs.find(j => j.clip_id === c.id && j.kind === "export" && (j.status === "queued" || j.status === "running"));
  const textsJob = c => jobs.find(j => j.clip_id === c.id && j.kind === "texts" && (j.status === "queued" || j.status === "running"));

  function drawTop() {
    const busy = project.status === "processing";
    const toExport = clips.filter(c => c.status === "editing" && (!c.has_export || c.export_stale) && !exportJob(c)).length;
    clear(topEl, pageTop(project.title, [clock(project.duration), { de: "Deutsch", en: "Englisch" }[project.language] || project.language, engineLabel(project.analysis_engine, app.meta.ai_models)].filter(Boolean).join(" · "),
      h("a", { class: "btn ghost", href: "#/projekte" }, icon("back"), "Alle Videos"),
      h("button", { class: "btn", disabled: busy, onclick: () => confirmBox("Highlights neu suchen?", "Vorschläge, die du noch nicht angenommen hast, werden ersetzt. Angenommene und fertige Clips bleiben.", "Neu suchen", async () => {
        try { await api.post(`/api/projects/${pid}/analyze`); toast("Analyse gestartet"); await refreshState(); await reload(); } catch (e) { toast(e.message, "err"); }
      }) }, icon("spark"), "Neu analysieren"),
      h("button", { class: "btn primary", id: "export-all", disabled: !toExport, onclick: async () => {
        try { const r = await api.post(`/api/projects/${pid}/export-accepted`); toast(`${r.queued} ${r.queued === 1 ? "Clip wird" : "Clips werden"} exportiert`); await refreshState(); } catch (e) { toast(e.message, "err"); }
      } }, icon("scissors"), toExport ? `${toExport} angenommene exportieren` : "Angenommene exportieren")),
      project.analysis_note ? h("div", { class: "note box" + (project.analysis_engine === "local" ? " warn" : ""), style: { marginBottom: "14px" } },
        project.analysis_note, project.analysis_engine === "local" && !app.state.has_api_key ? [" ", h("a", { href: "#/einstellungen" }, "API-Key eintragen")] : null) : null,
      project.status === "processing" ? h("div", { class: "note box", style: { marginBottom: "14px" } }, "Dieses Video wird gerade verarbeitet. Die Vorschläge erscheinen automatisch.") : null);
  }

  function drawList() {
    const order = { candidate: 0, editing: 1, done: 2, posted: 3, rejected: 4 };
    const sorted = [...clips].sort((a, b) => order[a.status] - order[b.status] || b.score - a.score);
    clear(listEl,
      sorted.map(c => h("button", { class: `scard ${c.status}${sel?.id === c.id ? " on" : ""}`, "data-clip": c.id, onclick: () => { if (sel?.id !== c.id) { sel = c; drawList(); drawEditor(); } } },
        scoreBadge(c.score),
        h("div", { class: "grow" },
          h("div", { class: "t" }, c.title || `Clip ${c.idx}`),
          h("div", { class: "m" },
            c.reason_label ? h("span", { class: "chip accent" }, c.reason_label) : null,
            h("span", { class: "chip mono" }, `${clock(c.start)}–${clock(c.end)}`),
            h("span", { class: "chip " + STATUS_CHIP[c.status] }, exportJob(c) ? "Export läuft" : STATUS[c.status]))))),
      h("button", { class: "btn", style: { marginTop: "4px" }, onclick: async () => {
        const t = ed?.video ? ed.video.currentTime : 0;
        const start = Math.max(0, Math.min(project.duration - 2, t)), end = Math.min(project.duration, start + 30);
        try { const c = await api.post(`/api/projects/${pid}/clips`, { start, end }); clips.push(c); sel = c; drawList(); drawEditor(); toast("Eigener Clip angelegt – Start und Ende kannst du jetzt einstellen"); }
        catch (e) { toast(e.message, "err"); }
      } }, icon("plus"), "Eigenen Clip anlegen"));
  }

  function closeEditor() {
    if (!ed) return;
    cancelAnimationFrame(ed.raf);
    try { ed.video.pause(); ed.video.removeAttribute("src"); ed.video.load(); } catch { /* */ }
    ed = null;
  }

  async function save(patch, quiet) {
    if (!sel) return;
    const id = sel.id;
    try {
      const c = await api.patch(`/api/clips/${id}`, patch);
      const i = clips.findIndex(x => x.id === id);
      if (i >= 0) clips[i] = c;
      if (sel.id === id) sel = c;
      drawList(); drawTop();
      if (ed && ed.clipId === id) { ed.drawActions(); }
      if (!quiet) toast("Gespeichert");
    } catch (e) { toast(e.message, "err"); }
  }

  function drawEditor() {
    closeEditor();
    if (!sel) {
      clear(editorEl, h("div", { class: "empty" }, icon("spark"), h("b", {}, project.status === "processing" ? "Analyse läuft …" : "Keine Vorschläge"),
        project.status === "processing" ? "Sobald das Video fertig verarbeitet ist, erscheinen hier die besten Momente." : "In diesem Video wurden keine passenden Stellen gefunden. Du kannst links einen eigenen Clip anlegen."));
      return;
    }
    const c0 = sel;
    const st = { start: c0.start, end: c0.end, mode: "preview", w0: 0, w1: 0, words: [], groups: [], gi: 0, lastKey: "" };
    const video = h("video", { playsinline: true, preload: "auto", src: `/api/projects/${pid}/video` });
    const capEl = h("div", { class: "cap" }), hookEl = h("div", { class: "hook hide" });
    const timeEl = h("span", {}, "0:00 / 0:00");
    const playBtn = h("button", { "aria-label": "Abspielen oder anhalten", onclick: toggle }, icon("play"));
    const phone = h("div", { class: "phone" }, video, hookEl, capEl,
      h("div", { class: "ctl" }, playBtn, h("button", { "aria-label": "Von vorn", onclick: () => { video.currentTime = st.start; video.play(); } }, icon("restart")), timeEl));
    const modeTabs = h("div", { class: "tabs", style: { marginBottom: "10px" } });
    ed = { clipId: c0.id, video, raf: 0, st };

    function cur() { return sel; }
    function tpl() { return tplMeta[cur().template] || tplMeta.pop; }
    function refreshWords() {
      st.words = tr.words.filter(w => { const m = (w.s + w.e) / 2; return m >= st.start && m <= st.end; });
      st.groups = groupWords(st.words, tpl()); st.gi = 0; st.lastKey = "";
      capEl.className = "cap " + (tplMeta[cur().template] ? cur().template : "pop");
      capEl.style.top = (CAP_Y[cur().template] || 70) + "%"; capEl.style.transform = "translateY(-50%)";
      clear(wordsEl, st.words.length ? st.words.map((w, i) => h("span", { "data-i": i, onclick: () => { video.currentTime = w.s; } }, w.w + " ")) : h("span", { class: "muted" }, "In diesem Ausschnitt wurde keine Sprache erkannt."));
    }
    function place() {
      if (st.mode !== "preview" || !video.videoWidth) return;
      const W = phone.clientWidth, H = phone.clientHeight, vw = H * video.videoWidth / video.videoHeight;
      const layout = cur().layout || "auto";
      const useFace = vw > W * 1.02 && (layout === "face" || (layout === "auto" && cur().focus_x != null));
      phone.classList.toggle("blur", !useFace);
      video.style.left = useFace ? Math.max(W - vw, Math.min(0, W / 2 - (cur().focus_x ?? 0.5) * vw)) + "px" : "0";
    }
    function toggle() {
      if (video.paused) { if (st.mode === "preview" && (video.currentTime < st.start - 0.05 || video.currentTime >= st.end - 0.05)) video.currentTime = st.start; video.play().catch(() => {}); }
      else video.pause();
    }
    function setMode(mode) {
      st.mode = mode;
      const c = cur();
      video.pause();
      phone.classList.toggle("blur", false);
      if (mode === "export") {
        video.style.left = "0"; video.style.width = "100%";
        video.src = `/api/clips/${c.id}/file?v=${encodeURIComponent(c.exported_at || "")}`;
        capEl.classList.add("hide"); hookEl.classList.add("hide");
      } else {
        video.style.width = "";
        video.src = `/api/projects/${pid}/video`;
        capEl.classList.remove("hide");
        video.addEventListener("loadedmetadata", () => { video.currentTime = st.start; place(); }, { once: true });
      }
      drawModeTabs();
    }
    function drawModeTabs() {
      const c = cur();
      const can = c.has_export && !c.export_stale;
      if (!can && st.mode === "export") { setMode("preview"); return; }
      clear(modeTabs,
        h("button", { class: st.mode === "preview" ? "on" : "", onclick: () => st.mode !== "preview" && setMode("preview") }, "Vorschau"),
        can ? h("button", { class: st.mode === "export" ? "on" : "", id: "tab-export", onclick: () => st.mode !== "export" && setMode("export") }, "Fertiger Clip") : null);
      modeTabs.classList.toggle("hide", !can);
    }

    // ----- Zuschnitt -----
    const selEl = h("div", { class: "sel" }), hA = h("div", { class: "hd a", role: "slider", tabindex: "0", "aria-label": "Start des Clips" }),
      hB = h("div", { class: "hd b", role: "slider", tabindex: "0", "aria-label": "Ende des Clips" }), ph = h("div", { class: "ph" }), aiEl = h("div", { class: "ai", title: "Vorschlag der KI" }), wave = h("div", { class: "wave" });
    const trim = h("div", { class: "trim" }, wave, aiEl, selEl, ph, hA, hB);
    const tStart = h("span", { class: "t" }), tEnd = h("span", { class: "t" }), tLen = h("span", { class: "chip mono" });
    const pos = t => (t - st.w0) / Math.max(0.001, st.w1 - st.w0) * 100;
    function setWindow() {
      const c = cur();
      st.w0 = Math.max(0, Math.min(st.start, c.ai_start ?? st.start) - 15);
      st.w1 = Math.min(project.duration, Math.max(st.end, c.ai_end ?? st.end) + 15);
      const loud = tr.loudness || [], a = Math.floor(st.w0), b = Math.ceil(st.w1), n = Math.max(1, b - a), stepN = Math.max(1, Math.ceil(n / 160));
      const bars = [];
      for (let i = a; i < b; i += stepN) {
        const seg = loud.slice(i, i + stepN), v = seg.length ? Math.max(...seg) : -60;
        bars.push(h("i", { style: { height: Math.max(6, Math.min(100, (v + 55) / 50 * 100)) + "%" } }));
      }
      clear(wave, bars);
      if (c.ai_start != null && c.origin === "ai") { aiEl.style.left = pos(c.ai_start) + "%"; aiEl.style.width = (pos(c.ai_end) - pos(c.ai_start)) + "%"; aiEl.classList.remove("hide"); } else aiEl.classList.add("hide");
      drawTrim();
    }
    function drawTrim() {
      selEl.style.left = pos(st.start) + "%"; selEl.style.width = (pos(st.end) - pos(st.start)) + "%";
      hA.style.left = pos(st.start) + "%"; hB.style.left = pos(st.end) + "%";
      tStart.textContent = clock(st.start, true); tEnd.textContent = clock(st.end, true);
      tLen.textContent = `Länge ${clock(st.end - st.start, true)}`;
      hA.setAttribute("aria-valuetext", clock(st.start, true)); hB.setAttribute("aria-valuetext", clock(st.end, true));
    }
    function setRange(start, end, which) {
      start = Math.round(start * 10) / 10; end = Math.round(end * 10) / 10;
      if (which === "a") start = Math.max(0, Math.min(start, end - 1, project.duration)), start = Math.max(start, end - 180);
      else end = Math.min(project.duration, Math.max(end, start + 1)), end = Math.min(end, start + 180);
      st.start = start; st.end = end;
      drawTrim();
    }
    async function commitRange() {
      if (Math.abs(st.start - cur().start) < 0.001 && Math.abs(st.end - cur().end) < 0.001) return;
      refreshWords();
      await save({ start: st.start, end: st.end }, true);
      setWindow(); drawModeTabs();
    }
    for (const [el, which] of [[hA, "a"], [hB, "b"]]) {
      el.addEventListener("pointerdown", e => { e.stopPropagation(); e.preventDefault(); el.setPointerCapture(e.pointerId); if (st.mode !== "preview") setMode("preview"); video.pause(); el._drag = true; });
      el.addEventListener("pointermove", e => {
        if (!el._drag) return;
        const r = trim.getBoundingClientRect(), t = st.w0 + Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * (st.w1 - st.w0);
        which === "a" ? setRange(t, st.end, "a") : setRange(st.start, t, "b");
        video.currentTime = which === "a" ? st.start : Math.max(st.start, st.end - 0.05);
      });
      const up = () => { if (el._drag) { el._drag = false; commitRange(); } };
      el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
      el.addEventListener("keydown", e => {
        if (!["ArrowLeft", "ArrowRight"].includes(e.key)) return;
        e.preventDefault(); nudge(which, (e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 1 : 0.1));
      });
    }
    trim.addEventListener("pointerdown", e => {
      if (st.mode !== "preview") return;
      const r = trim.getBoundingClientRect(), t = st.w0 + (e.clientX - r.left) / r.width * (st.w1 - st.w0);
      video.currentTime = Math.max(st.start, Math.min(st.end - 0.05, t));
    });
    let nudgeTimer = null;
    function nudge(which, d) {
      if (st.mode !== "preview") setMode("preview");
      which === "a" ? setRange(st.start + d, st.end, "a") : setRange(st.start, st.end + d, "b");
      video.pause(); video.currentTime = which === "a" ? st.start : Math.max(st.start, st.end - 0.05);
      clearTimeout(nudgeTimer); nudgeTimer = setTimeout(commitRange, 500);
    }
    const nb = (which, d, label) => h("button", { class: "btn sm", title: label, "aria-label": label, onclick: () => nudge(which, d) }, d < 0 ? "−0,5" : "+0,5");

    // ----- Felder -----
    const titleIn = h("input", { type: "text", value: c0.title || "", id: "clip-title", "aria-label": "Arbeitstitel", onchange: e => save({ title: e.target.value }, true) });
    const scoreVal = h("b", { class: "mono", style: { fontSize: "15px", minWidth: "30px", textAlign: "right" } }, c0.score);
    const scoreNote = h("span", { class: "note" });
    const scoreIn = h("input", { type: "range", min: 0, max: 100, step: 1, value: c0.score, id: "clip-score", "aria-label": "Dein Score",
      oninput: e => { scoreVal.textContent = e.target.value; }, onchange: e => save({ user_score: +e.target.value }, true).then(drawScore) });
    function drawScore() {
      const c = cur();
      scoreIn.value = c.score; scoreVal.textContent = c.score;
      clear(scoreNote, c.origin === "manual" ? "Eigener Clip – du bewertest selbst." : c.user_score == null ? `KI-Bewertung: ${c.ai_score}. Zieh den Regler, um sie zu überschreiben.` :
        [`Deine Bewertung (KI: ${c.ai_score}). `, h("a", { href: "#", onclick: e => { e.preventDefault(); save({ user_score: null }, true).then(drawScore); } }, "KI-Wert übernehmen")]);
    }
    const hookIn = h("input", { type: "text", value: c0.hook || "", id: "clip-hook", placeholder: "Text für die ersten Sekunden", maxlength: 120,
      oninput: e => { hookEl.textContent = e.target.value; }, onchange: e => save({ hook: e.target.value }, true) });
    const tplBox = h("div", { class: "tpls" });
    function drawTpls() {
      clear(tplBox, app.meta.templates.map(t => h("button", { class: "tpl" + (cur().template === t.id ? " on" : ""), title: t.desc, "data-tpl": t.id,
        onclick: async () => { await save({ template: t.id }, true); refreshWords(); drawTpls(); drawModeTabs(); } },
        h("div", { class: "pv" }, h("div", { class: "cap " + t.id }, h("span", { class: t.id === "clean" ? "said" : "" }, t.upper ? "SO " : "So "), h("span", { class: "act" }, t.upper ? "SIEHT’S" : "sieht’s"))),
        h("small", {}, t.label))));
    }
    const layoutSel = select([{ value: "auto", label: "Automatisch" }, { value: "face", label: "Gesicht folgen (Zoom)" }, { value: "blur", label: "Ganzes Bild, unscharfer Hintergrund" }], c0.layout || "auto",
      { id: "clip-layout", onchange: async e => { await save({ layout: e.target.value }, true); place(); drawModeTabs(); } });
    const campSel = select([{ value: "", label: "Keine Kampagne" }, ...campaigns.map(k => ({ value: k.id, label: k.name }))], c0.campaign_id ?? "",
      { id: "clip-campaign", onchange: e => save({ campaign_id: e.target.value ? +e.target.value : null }, true) });
    const wordsEl = h("div", { class: "words" });
    const actionsEl = h("div", { class: "col" }), textsEl = h("div");
    let tab = Object.keys(app.meta.text_platforms)[0];

    ed.drawActions = function drawActions() {
      const c = cur(), job = exportJob(c);
      const ready = c.has_export && !c.export_stale;
      clear(actionsEl,
        h("div", { class: "row wrap" },
          c.status === "candidate" ? [
            h("button", { class: "btn good", id: "btn-accept", onclick: () => move("editing") }, icon("check"), "Annehmen"),
            h("button", { class: "btn danger", id: "btn-reject", onclick: () => move("rejected") }, icon("x"), "Verwerfen")] : null,
          c.status === "rejected" ? h("button", { class: "btn", onclick: () => move("candidate") }, icon("restart"), "Zurückholen") : null,
          c.status !== "rejected" ? h("button", { class: "btn primary", id: "btn-export", disabled: !!job, onclick: async () => {
            try { await api.post(`/api/clips/${c.id}/export`); toast("Export gestartet"); await refreshState(); await reloadClip(c.id); } catch (e) { toast(e.message, "err"); }
          } }, icon("scissors"), job ? "Export läuft …" : c.has_export ? (c.export_stale ? "Neu exportieren" : "Erneut exportieren") : "Als 9:16 exportieren") : null,
          ready ? h("a", { class: "btn", id: "btn-download", href: `/api/clips/${c.id}/file?download=1` }, icon("download"), "Herunterladen") : null,
          ready ? h("button", { class: "btn", onclick: async () => { try { const r = await api.post(`/api/clips/${c.id}/reveal`); toast("Ordner: " + r.folder, "ok", 6000); } catch (e) { toast(e.message, "err"); } } }, icon("folder"), "Ordner öffnen") : null,
          ready ? h("button", { class: "btn", id: "btn-post", onclick: () => postDialog(c, campaigns, async () => { await refreshState(); await reloadClip(c.id); }) }, icon("post"), "Als gepostet eintragen") : null,
          h("button", { class: "btn ghost icon right", title: "Clip löschen", "aria-label": "Clip löschen", onclick: () => confirmBox("Clip löschen?", "Der Clip wird mit Export und eingetragenen Posts gelöscht.", "Löschen", async () => {
            try { await api.del(`/api/clips/${c.id}`); clips = clips.filter(x => x.id !== c.id); sel = clips.find(x => x.status === "candidate") || clips[0] || null; drawList(); drawEditor(); drawTop(); } catch (e) { toast(e.message, "err"); }
          }, true) }, icon("trash"))),
        job ? h("div", {}, h("div", { class: "bar" }, h("i", { style: { width: (job.progress || 0) * 100 + "%" } })), h("div", { class: "note", style: { marginTop: "5px" } }, job.message || "Wartet …")) : null,
        c.has_export && c.export_stale && !job ? h("div", { class: "note box warn" }, "Du hast seit dem letzten Export etwas geändert. Exportiere neu, damit der fertige Clip dazu passt.") : null,
        c.posts?.length ? h("div", { class: "note box" }, c.posts.map(p => h("div", { class: "spread" }, h("span", {}, `${p.platform}${p.campaign_name ? " · " + p.campaign_name : ""}`), h("span", { class: "mono" }, `${num(p.views)} Views · ${eur(p.earned || 0, true)}`)))) : null);
      drawTexts();
    };
    function drawTexts() {
      const c = cur(), t = c.texts, job = textsJob(c);
      if (!t && !c.has_export && !job) { clear(textsEl); return; }
      const names = app.meta.text_platforms, cur_ = t?.[tab];
      const row = (k, text) => h("div", { class: "copyrow" }, h("span", { class: "k" }, k), h("p", {}, text),
        h("button", { class: "btn sm icon ghost", title: "Kopieren", "aria-label": "Kopieren", onclick: () => copyText(text) }, icon("copy")));
      clear(textsEl, h("div", { class: "sect" },
        h("div", { class: "eyebrow" }, "Titel, Beschreibung, Hashtags",
          c.texts_engine ? h("span", { class: "chip " + (c.texts_engine === "local" ? "warn" : "accent"), style: { textTransform: "none", letterSpacing: 0 } }, c.texts_engine === "local" ? "ohne KI" : "von Claude") : null),
        t ? h("div", { class: "col" },
          h("div", { class: "spread wrap" },
            h("div", { class: "tabs" }, Object.entries(names).map(([k, label]) => h("button", { class: k === tab ? "on" : "", onclick: () => { tab = k; drawTexts(); } }, label))),
            h("button", { class: "btn sm", disabled: !!job, id: "btn-texts", onclick: regen }, icon("refresh"), job ? "Schreibe …" : "Neu schreiben")),
          t._note ? h("div", { class: "note" }, t._note) : null,
          (cur_?.titles || []).map((x, i) => row(String(i + 1), x)),
          cur_?.description ? row("B", cur_.description) : null,
          cur_?.hashtags?.length ? row("#", cur_.hashtags.join(" ")) : null,
          h("div", {}, h("button", { class: "btn sm ghost", onclick: () => copyText([cur_?.titles?.[0], cur_?.description, (cur_?.hashtags || []).join(" ")].filter(Boolean).join("\n\n")) }, icon("copy"), "Alles für diese Plattform kopieren")))
          : h("button", { class: "btn sm", disabled: !!job, onclick: regen }, icon("wand"), job ? "Schreibe …" : "Texte schreiben")));
    }
    async function regen() {
      try { await api.post(`/api/clips/${cur().id}/texts`); await refreshState(); jobs = app.state.jobs; drawTexts(); } catch (e) { toast(e.message, "err"); }
    }
    async function move(status) {
      const id = cur().id;
      try {
        const r = await api.post(`/api/clips/${id}/move`, { status });
        const i = clips.findIndex(x => x.id === id); clips[i] = r.clip; sel = r.clip;
        if (status === "rejected") { const nxt = clips.find(x => x.status === "candidate"); if (nxt) { sel = nxt; drawList(); drawTop(); drawEditor(); return; } }
        drawList(); drawTop(); ed.drawActions();
        toast(status === "editing" ? "Angenommen" : status === "rejected" ? "Verworfen" : "Zurückgeholt");
      } catch (e) { toast(e.message, "err"); }
    }

    // ----- Schleife: Untertitel, Hook, Zeit, Abspielkopf -----
    function tick() {
      ed.raf = requestAnimationFrame(tick);
      const t = video.currentTime;
      if (st.mode === "export") { timeEl.textContent = `${clock(t)} / ${clock(video.duration || 0)}`; return; }
      if (!video.paused && t >= st.end) { video.pause(); video.currentTime = st.start; }
      timeEl.textContent = `${clock(Math.max(0, t - st.start))} / ${clock(st.end - st.start)}`;
      ph.style.left = Math.max(0, Math.min(100, pos(t))) + "%";
      const c = cur();
      const showHook = c.hook_enabled && (hookIn.value || "").trim() && t - st.start >= -0.05 && t - st.start < (settings.hook_seconds || 2.5);
      hookEl.classList.toggle("hide", !showHook);
      const gs = st.groups;
      if (!gs.length) { if (st.lastKey) { capEl.replaceChildren(); st.lastKey = ""; } return; }
      let gi = st.gi;
      if (gi >= gs.length || t < gs[gi].start) gi = 0;
      while (gi < gs.length - 1 && t >= gs[gi + 1].start) gi++;
      st.gi = gi;
      const g = gs[gi];
      let act = -1;
      if (t >= g.start && t < g.until) g.words.forEach((w, i) => { if (t >= w.s) act = i; });
      const key = gi + ":" + act;
      if (key === st.lastKey) return;
      st.lastKey = key;
      if (act < 0) { capEl.replaceChildren(); return; }
      clear(capEl, g.words.map((w, i) => h("span", { class: i === act ? "act" : i < act ? "said" : "" }, w.w)));
      const idx = st.words.indexOf(g.words[act]);
      wordsEl.querySelector(".now")?.classList.remove("now");
      wordsEl.querySelector(`[data-i="${idx}"]`)?.classList.add("now");
    }
    video.addEventListener("play", () => clear(playBtn, icon("pause")));
    video.addEventListener("pause", () => clear(playBtn, icon("play")));
    video.addEventListener("loadedmetadata", () => { video.currentTime = st.start; place(); }, { once: true });
    video.addEventListener("error", () => { if (video.getAttribute("src")) toast("Das Video kann im Browser nicht abgespielt werden.", "err"); });

    hookEl.textContent = c0.hook || "";
    clear(editorEl,
      h("div", { class: "editor" },
        h("div", {}, modeTabs, phone, h("div", { class: "note center", style: { marginTop: "10px" } }, "Vorschau – der fertige Clip wird beim Export in 1080 × 1920 gerendert.")),
        h("div", {},
          h("div", { class: "sect" },
            h("div", { class: "row" }, h("div", { class: "grow" }, titleIn)),
            c0.reason ? h("div", { class: "note", style: { marginTop: "8px" } }, c0.reason_label ? h("b", { class: "dim" }, c0.reason_label + " · ") : null, c0.reason) : null),
          h("div", { class: "sect" },
            h("div", { class: "eyebrow" }, "Zuschnitt", h("span", { class: "right" }), tLen),
            trim,
            h("div", { class: "trimrow", style: { marginTop: "9px" } },
              h("div", { class: "side-a" }, h("span", { class: "muted" }, "Start"), nb("a", -0.5, "Start eine halbe Sekunde früher"), tStart, nb("a", 0.5, "Start eine halbe Sekunde später")),
              h("div", { class: "side-b" }, h("span", { class: "muted" }, "Ende"), nb("b", -0.5, "Ende eine halbe Sekunde früher"), tEnd, nb("b", 0.5, "Ende eine halbe Sekunde später"))),
            c0.origin === "ai" ? h("div", { style: { marginTop: "8px" } }, h("button", { class: "btn sm ghost", onclick: () => { setRange(cur().ai_start, cur().ai_end, "b"); st.start = cur().ai_start; drawTrim(); commitRange(); video.currentTime = st.start; } }, icon("restart"), "Auf KI-Vorschlag zurücksetzen")) : null),
          h("div", { class: "sect" },
            h("div", { class: "eyebrow" }, "Viral-Score"),
            h("div", { class: "row" }, scoreIn, scoreVal), scoreNote),
          h("div", { class: "sect" },
            h("div", { class: "eyebrow" }, "Hook-Text oben im Bild", h("span", { class: "right" }), switchEl(!!c0.hook_enabled, v => save({ hook_enabled: v }, true), "Hook-Text einblenden")),
            hookIn),
          h("div", { class: "sect" }, h("div", { class: "eyebrow" }, "Untertitel-Vorlage"), tplBox),
          h("div", { class: "sect" }, h("div", { class: "form two" }, field("Bildausschnitt", layoutSel), field("Kampagne", campSel, campaigns.length ? "Regeln der Kampagne fließen in die Texte ein." : "Kampagnen legst du unter „Einnahmen“ an."))),
          h("div", { class: "sect" }, actionsEl),
          textsEl,
          h("div", { class: "sect" }, h("div", { class: "eyebrow" }, "Transkript des Ausschnitts"), wordsEl))));
    ed.drawModeTabs = drawModeTabs; ed.setMode = setMode;
    refreshWords(); setWindow(); drawScore(); drawTpls(); drawModeTabs(); ed.drawActions();
    ed.raf = requestAnimationFrame(tick);
    ed.toggle = toggle;
  }

  async function reloadClip(id) {
    try {
      const c = await api.get(`/api/clips/${id}`);
      const i = clips.findIndex(x => x.id === id);
      if (i >= 0) clips[i] = c; else clips.push(c);
      if (sel?.id === id) sel = c;
      jobs = app.state.jobs;
      drawList(); drawTop();
      if (ed?.clipId === id) { ed.drawActions(); ed.drawModeTabs(); }
    } catch { /* gelöscht */ }
  }
  async function reload() {
    project = await api.get(`/api/projects/${pid}`);
    clips = project.clips;
    sel = clips.find(c => c.id === sel?.id) || clips.find(c => c.status === "candidate") || clips[0] || null;
    jobs = app.state.jobs;
    drawTop(); drawList(); drawEditor();
  }

  clear(root, topEl, h("div", { class: "review" }, h("div", {}, listEl), editorEl));
  drawTop(); drawList(); drawEditor();

  const onKey = e => {
    if (e.code !== "Space" || /INPUT|TEXTAREA|SELECT|BUTTON|A/.test(document.activeElement?.tagName || "") || document.querySelector(".modal-back")) return;
    e.preventDefault(); ed?.toggle?.();
  };
  document.addEventListener("keydown", onKey);
  // Prüfzeit messen (für „so viel Zeit spart dir die App“) – nur solange das Fenster aktiv ist
  const beat = setInterval(() => { if (document.visibilityState === "visible" && document.hasFocus()) api.post(`/api/projects/${pid}/review-time`, { seconds: 15 }).catch(() => {}); }, 15000);

  return {
    cleanup: () => { clearInterval(beat); document.removeEventListener("keydown", onKey); closeEditor(); },
    onState: (st, finished) => {
      jobs = st.jobs;
      const mine = finished.filter(j => j.project_id === pid);
      if (mine.some(j => !j.clip_id)) { reload(); return; }
      for (const j of mine) if (j.clip_id) reloadClip(j.clip_id).then(() => { if (ed?.clipId === j.clip_id && j.kind === "export" && j.status === "done" && sel?.has_export && !sel.export_stale) ed.setMode("export"); });
      if (ed && sel && (exportJob(sel) || textsJob(sel))) ed.drawActions();
      if (st.jobs.some(j => j.project_id === pid && j.clip_id && j.status !== "done")) drawList();
    },
  };
}
