// Videos: Import per Drag & Drop oder Link, Projektliste.
import { api } from "../api.js";
import { pageTop, refreshState, confirmBox } from "../app.js";
import { h, clear, icon, clock, toast, dateDE } from "../ui.js";

const uploads = [];        // laufende Uploads überleben einen Seitenwechsel

export async function render(root) {
  const listEl = h("div", { class: "plist" });
  const upEl = h("div", { class: "col" });
  const fileInput = h("input", { type: "file", accept: "video/*,.mkv,.mov,.mp4,.webm,.avi,.m4v", multiple: true, class: "hide", id: "file-input",
    onchange: e => { addFiles(e.target.files); e.target.value = ""; } });
  const drop = h("div", { class: "drop", tabindex: "0", role: "button", "aria-label": "Video hochladen",
    onclick: () => fileInput.click(), onkeydown: e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } },
    ondragover: e => { e.preventDefault(); drop.classList.add("over"); }, ondragleave: () => drop.classList.remove("over"),
    ondrop: e => { e.preventDefault(); drop.classList.remove("over"); addFiles(e.dataTransfer.files); } },
    h("div", {}, icon("upload"), h("b", {}, "Video hierher ziehen"), h("span", {}, "oder klicken und Datei auswählen · MP4, MOV, MKV, WEBM")));

  const urlInput = h("input", { type: "url", placeholder: "https://… Link zum Video", id: "link-url" });
  const rights = h("input", { type: "checkbox", id: "link-rights" });
  const linkBox = h("section", { class: "panel" },
    h("div", { class: "head" }, icon("link"), h("h2", {}, "Per Link importieren")),
    h("div", { class: "col" }, urlInput,
      h("label", { class: "check" }, rights, h("span", {}, "Ich habe die Rechte an diesem Material oder eine Kampagnenfreigabe dafür.")),
      h("div", {}, h("button", { class: "btn", onclick: async e => {
        const b = e.currentTarget; b.disabled = true;
        try {
          await api.post("/api/projects/link", { url: urlInput.value, rights_confirmed: rights.checked });
          urlInput.value = ""; rights.checked = false; toast("Download gestartet"); await refreshState(); await load();
        } catch (err) { toast(err.message, "err"); } finally { b.disabled = false; }
      } }, icon("download"), "Video laden")),
      h("div", { class: "note" }, "Funktioniert mit direkten Videolinks und vielen Plattformen. Bitte nur Material laden, das du verwenden darfst.")));

  function addFiles(files) {
    for (const f of files) {
      const u = { name: f.name, p: 0, err: null };
      uploads.push(u); drawUploads();
      api.upload(f, p => { u.p = p; drawUploads(); })
        .then(async () => { uploads.splice(uploads.indexOf(u), 1); drawUploads(); toast(`„${f.name}“ hochgeladen – Analyse läuft`); await refreshState(); load(); })
        .catch(err => { u.err = err.message; drawUploads(); toast(err.message, "err"); });
    }
  }
  function drawUploads() {
    clear(upEl, uploads.map(u => h("div", { class: "panel", style: { padding: "12px 14px" } },
      h("div", { class: "spread" }, h("b", { class: "ellipsis" }, u.name),
        u.err ? h("button", { class: "btn sm ghost", onclick: () => { uploads.splice(uploads.indexOf(u), 1); drawUploads(); } }, "Schließen") : h("span", { class: "mono dim" }, Math.round(u.p * 100) + " %")),
      u.err ? h("div", { class: "note warn box", style: { marginTop: "8px" } }, u.err) : h("div", { class: "bar", style: { marginTop: "8px" } }, h("i", { style: { width: u.p * 100 + "%" } })))));
  }

  const STATUS = { imported: ["Importiert", ""], processing: ["Wird verarbeitet", "accent"], ready: ["Bereit", "good"], error: ["Fehler", "crit"], sample: ["Beispiel", "warn"] };
  let projects = [];
  async function load() {
    projects = await api.get("/api/projects");
    drawList();
  }
  function drawList() {
    if (!projects.length) {
      clear(listEl, h("div", { class: "panel empty" }, icon("film"), h("b", {}, "Noch keine Videos"), "Zieh oben dein erstes langes Video hinein. ClipPilot transkribiert es und schlägt die besten Momente vor."));
      return;
    }
    clear(listEl, projects.map(p => {
      const [label, cls] = STATUS[p.status] || [p.status, ""];
      const c = p.clip_counts || {};
      const open = p.status === "ready" || (p.status === "error" && (c.candidate || c.editing || c.done));
      const card = h(open ? "a" : "div", { class: "pcard", href: open ? `#/projekt/${p.id}` : null, "data-project": p.id },
        h("div", { class: "th", style: p.filename && p.status !== "processing" || p.duration ? { backgroundImage: `url(/api/projects/${p.id}/thumb)` } : null }, p.filename ? null : icon("film")),
        h("div", { class: "grow" },
          h("h3", { class: "ellipsis" }, p.title),
          h("div", { class: "meta" },
            h("span", { class: "chip " + cls }, label),
            p.duration ? h("span", { class: "chip mono" }, clock(p.duration)) : null,
            p.language ? h("span", { class: "chip" }, { de: "Deutsch", en: "Englisch" }[p.language] || p.language.toUpperCase()) : null,
            c.candidate ? h("span", { class: "chip" }, `${c.candidate} zu prüfen`) : null,
            c.editing ? h("span", { class: "chip accent" }, `${c.editing} in Arbeit`) : null,
            c.done ? h("span", { class: "chip good" }, `${c.done} fertig`) : null,
            c.posted ? h("span", { class: "chip gold" }, `${c.posted} gepostet`) : null,
            h("span", { class: "chip" }, dateDE(p.created_at))),
          p.job ? h("div", { style: { marginTop: "10px" } },
            h("div", { class: "bar" }, h("i", { style: { width: (p.job.progress || 0) * 100 + "%" } })),
            h("div", { class: "note", style: { marginTop: "5px" } }, p.job.message || "Wartet …")) : null,
          p.status === "error" ? h("div", { class: "note warn box", style: { marginTop: "9px" } }, p.error || "Unbekannter Fehler") : null,
          p.status === "sample" ? h("div", { class: "note", style: { marginTop: "7px" } }, "Beispielprojekt ohne Video – nur zum Ansehen der Auswertungen.") : null),
        h("div", { class: "acts row" },
          p.status === "error" && p.filename ? h("button", { class: "btn sm", onclick: async e => { e.preventDefault(); try { await api.post(`/api/projects/${p.id}/analyze`); await refreshState(); load(); } catch (err) { toast(err.message, "err"); } } }, icon("refresh"), "Erneut versuchen") : null,
          open ? h("span", { class: "btn sm primary" }, "Prüfen", icon("chevron")) : null,
          p.status !== "processing" ? h("button", { class: "btn sm icon ghost", title: "Projekt löschen", "aria-label": `Projekt ${p.title} löschen`, onclick: e => {
            e.preventDefault(); e.stopPropagation();
            confirmBox("Projekt löschen?", `„${p.title}“ wird mit allen Clips, Exporten und eingetragenen Posts gelöscht. Das lässt sich nicht rückgängig machen.`, "Löschen",
              async () => { try { await api.del(`/api/projects/${p.id}`); toast("Projekt gelöscht"); await refreshState(); load(); } catch (err) { toast(err.message, "err"); } }, true);
          } }, icon("trash")) : null));
      return card;
    }));
  }

  clear(root, pageTop("Videos", "Langes Video rein, fertige Clips raus"),
    h("div", { class: "grid in" }, h("div", { class: "grid g21" }, h("div", { class: "col" }, drop, fileInput, upEl), linkBox), listEl));
  drawUploads();
  await load();
  return { onState: (st, finished) => {
    const active = st.jobs.filter(j => j.status === "queued" || j.status === "running");
    if (finished.length) { load(); return; }
    let changed = false;
    for (const p of projects) {
      const j = active.find(x => x.project_id === p.id && !x.clip_id);
      if (j) { p.job = j; changed = true; }
    }
    if (changed) drawList();
  } };
}
