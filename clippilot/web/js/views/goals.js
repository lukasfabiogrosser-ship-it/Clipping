// Ziele: Tages- und Monatsziel setzen, Hochrechnung, Zeitersparnis, Serie, Erfolge.
import { api } from "../api.js";
import { pageTop, refreshState } from "../app.js";
import { h, clear, icon, toast, field, eur, num } from "../ui.js";
import { achievementsGrid, projectionBlock, timeSavedBlock } from "./cockpit.js";

export async function render(root) {
  const body = h("div", { class: "grid in" });
  async function load() {
    const [s, d] = await Promise.all([api.get("/api/settings"), api.get("/api/dashboard")]);
    const clips = h("input", { type: "number", min: 0, max: 100, step: 1, value: s.goal_clips_per_day, id: "goal-clips" });
    const month = h("input", { type: "number", min: 0, step: 50, value: s.goal_month_eur, id: "goal-month" });
    const manual = h("input", { type: "number", min: 1, max: 600, step: 1, value: s.manual_minutes_per_clip, id: "goal-manual" });
    const perDay = d.month.goal ? d.month.goal / d.month.days : 0;
    clear(body,
      h("div", { class: "grid g12" },
        h("section", { class: "panel hud" },
          h("div", { class: "head" }, icon("target"), h("h2", {}, "Deine Ziele")),
          h("div", { class: "form" },
            field("Clips pro Tag", clips, "Daraus wird deine Tagesquest."),
            field("Einnahmen pro Monat (€)", month, perDay ? `Das sind rund ${eur(perDay, true)} pro Tag.` : null),
            field("So lange brauchst du von Hand pro Clip (Minuten)", manual, "Vergleichswert für die Zeitersparnis."),
            h("div", {}, h("button", { class: "btn primary", id: "goal-save", onclick: async () => {
              try { await api.post("/api/settings", { goal_clips_per_day: +clips.value || 0, goal_month_eur: +month.value || 0, manual_minutes_per_clip: +manual.value || 1 }); toast("Ziele gespeichert"); await refreshState(); await load(); }
              catch (e) { toast(e.message, "err"); }
            } }, icon("check"), "Ziele speichern")))),
        h("div", { class: "grid" },
          h("div", { class: "grid g2" },
            h("section", { class: "panel" }, h("div", { class: "head" }, icon("chart"), h("h2", {}, "Bei deinem aktuellen Tempo")), projectionBlock(d)),
            h("section", { class: "panel" }, h("div", { class: "head" }, icon("clock"), h("h2", {}, "Zeitersparnis")), timeSavedBlock(d.time_saved))),
          h("section", { class: "panel" },
            h("div", { class: "head" }, icon("flame"), h("h2", {}, "Serie")),
            h("div", { class: "row wrap", style: { gap: "22px" } },
              h("div", { class: "streak" + (d.streak.current ? "" : " off") }, h("div", { class: "fl" }, icon("flame")),
                h("div", {}, h("div", { class: "num" }, d.streak.current, h("small", {}, d.streak.current === 1 ? " Tag in Folge" : " Tage in Folge")),
                  h("div", { class: "note" }, d.streak.current ? (d.streak.today_done ? "Heute schon gepostet – Serie gesichert." : "Poste heute einen Clip, damit die Serie nicht reißt.") : "Poste heute einen Clip, um eine Serie zu starten."))),
              h("div", {}, h("div", { class: "eyebrow" }, "Längste Serie"), h("div", { class: "num", style: { fontSize: "20px", marginTop: "6px" } }, d.streak.best, h("small", {}, " Tage"))),
              h("div", {}, h("div", { class: "eyebrow" }, "Clips gepostet"), h("div", { class: "num", style: { fontSize: "20px", marginTop: "6px" } }, num(d.totals.posted))),
              h("div", {}, h("div", { class: "eyebrow" }, "Views gesamt"), h("div", { class: "num", style: { fontSize: "20px", marginTop: "6px" } }, num(d.totals.views))))))),
      h("section", { class: "panel" },
        h("div", { class: "head" }, icon("trophy"), h("h2", {}, "Erfolge"), h("span", { class: "right" }, `${d.achievements.filter(a => a.done).length} von ${d.achievements.length} freigeschaltet`)),
        achievementsGrid(d.achievements)));
  }
  clear(root, pageTop("Ziele", "Was du erreichen willst – und wie nah du dran bist"), body);
  await load();
  return {};
}
