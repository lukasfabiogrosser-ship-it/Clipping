// Pipeline: Rohvideo → Kandidaten → In Bearbeitung → Fertig → Gepostet, Karten per Drag & Drop.
import { api } from "../api.js";
import { pageTop, refreshState } from "../app.js";
import { h, clear, icon, clock, toast, num, eur, select } from "../ui.js";
import { postDialog } from "./postdialog.js";

const COLS = [
  ["raw", "Rohvideo", "#63768a"], ["candidate", "Kandidaten", "#a3b4c4"], ["editing", "In Bearbeitung", "#4fd8ff"],
  ["done", "Fertig", "#2fd17a"], ["posted", "Gepostet", "#ffb547"],
];

export async function render(root) {
  const board = h("div", { class: "kanban" });
  let data = null, campaigns = [], dragging = null;

  async function load() {
    [data, campaigns] = await Promise.all([api.get("/api/pipeline"), api.get("/api/campaigns")]);
    draw();
  }
  async function move(clip, status) {
    if (status === clip.status) return;
    if (status === "posted") { postDialog(clip, campaigns, async () => { await refreshState(); load(); }); return; }
    try {
      const r = await api.post(`/api/clips/${clip.id}/move`, { status });
      if (r.queued_export) toast("Export gestartet – die Karte wandert nach „Fertig“, sobald er durch ist");
      await refreshState(); await load();
    } catch (e) { toast(e.message, "err"); }
  }
  function card(c) {
    const el = h("a", { class: "kcard", draggable: "true", href: c.is_sample ? null : `#/projekt/${c.project_id}/${c.id}`, "data-clip": c.id,
      ondragstart: e => { dragging = c; el.classList.add("drag"); e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(c.id)); },
      ondragend: () => { dragging = null; el.classList.remove("drag"); board.querySelectorAll(".over").forEach(x => x.classList.remove("over")); } },
      h("div", { class: "th", style: c.is_sample ? null : { backgroundImage: `url(/api/clips/${c.id}/thumb)` } },
        h("span", { class: "sc" }, c.score), h("span", { class: "du" }, clock(c.duration))),
      h("b", {}, c.title || `Clip ${c.idx}`), h("small", { class: "ellipsis" }, c.project_title),
      c.job ? h("div", { style: { marginTop: "7px" } }, h("div", { class: "bar" }, h("i", { style: { width: (c.job.progress || 0) * 100 + "%" } })), h("small", {}, "Export läuft …")) : null,
      h("div", { class: "ft" },
        c.has_export && c.export_stale && !c.job ? h("span", { class: "chip warn", title: "Seit dem letzten Export geändert" }, "geändert") : null,
        c.status === "posted" ? [h("span", { class: "chip" }, `${num(c.views)} Views`), h("span", { class: "chip gold" }, eur(c.earned || 0, true))] : null,
        c.is_sample ? h("span", { class: "chip warn" }, "Beispiel") : null),
      // Für Tastatur und Touch: Verschieben ohne Ziehen
      select([{ value: "", label: "Verschieben nach …" }, ...COLS.slice(1).filter(([k]) => k !== c.status).map(([k, l]) => ({ value: k, label: l })), ...(c.status !== "rejected" ? [{ value: "rejected", label: "Verwerfen" }] : [])], "",
        { "aria-label": "Clip verschieben", style: { marginTop: "7px", height: "28px", fontSize: "12px" }, onclick: e => e.preventDefault(),
          onchange: e => { const v = e.target.value; e.target.value = ""; if (v) move(c, v); } }));
    return el;
  }
  function rawCard(p) {
    const ready = p.status === "ready";
    return h("a", { class: "kcard raw", href: ready ? `#/projekt/${p.id}` : "#/projekte" },
      h("div", { class: "th", style: p.duration ? { backgroundImage: `url(/api/projects/${p.id}/thumb)` } : null }, p.duration ? h("span", { class: "du" }, clock(p.duration)) : null),
      h("b", {}, p.title),
      p.job ? h("div", { style: { marginTop: "7px" } }, h("div", { class: "bar" }, h("i", { style: { width: (p.job.progress || 0) * 100 + "%" } })), h("small", {}, p.job.message || "Wartet …")) : null,
      h("div", { class: "ft" }, h("span", { class: "chip " + (p.status === "error" ? "crit" : p.status === "processing" ? "accent" : "") }, { ready: "analysiert", processing: "wird verarbeitet", error: "Fehler", imported: "importiert" }[p.status] || p.status)));
  }
  function draw() {
    clear(board, COLS.map(([key, label, color]) => {
      const items = data[key] || [];
      const col = h("section", { class: "kcol", "data-col": key, "aria-label": label },
        h("header", {}, h("i", { style: { background: color, boxShadow: `0 0 8px ${color}` } }), label, h("span", { class: "n" }, items.length)),
        h("div", { class: "cards" }, items.length ? items.map(key === "raw" ? rawCard : card)
          : h("div", { class: "note center", style: { padding: "18px 8px" } }, { raw: "Noch kein Video importiert.", candidate: "Keine offenen Vorschläge.", editing: "Nichts in Arbeit.", done: "Noch nichts fertig.", posted: "Noch nichts gepostet." }[key])));
      if (key !== "raw") {
        col.addEventListener("dragover", e => { if (dragging && dragging.status !== key) { e.preventDefault(); col.classList.add("over"); } });
        col.addEventListener("dragleave", e => { if (!col.contains(e.relatedTarget)) col.classList.remove("over"); });
        col.addEventListener("drop", e => { e.preventDefault(); col.classList.remove("over"); const c = dragging; dragging = null; if (c) move(c, key); });
      }
      return col;
    }));
  }

  clear(root, pageTop("Pipeline", "Karten ziehen, um den Status zu ändern. Ziehst du auf „Fertig“, startet der Export."), board);
  await load();
  // Während ein Export läuft, nur die Fortschrittsbalken anpassen – die Karten bleiben stehen, damit man weiter ziehen kann.
  let known = new Set(), pending = false;
  board.addEventListener("dragend", () => { if (pending) { pending = false; load(); } });
  return { onState: (st, finished) => {
    const active = st.jobs.filter(j => j.status === "queued" || j.status === "running");
    const ids = new Set(active.map(j => j.id));
    const fresh = active.some(j => !known.has(j.id));
    known = ids;
    if (finished.length || fresh) { if (dragging) pending = true; else load(); return; }
    for (const j of active) {
      const el = j.clip_id ? board.querySelector(`.kcard[data-clip="${j.clip_id}"] .bar i`) : null;
      if (el) el.style.width = (j.progress || 0) * 100 + "%";
    }
  } };
}
