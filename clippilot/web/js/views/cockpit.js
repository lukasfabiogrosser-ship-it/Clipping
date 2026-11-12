// Cockpit: was heute ansteht, Tagesquest, Zahlen, Monatsziel, Hochrechnung, Erfolge.
import { api } from "../api.js";
import { app, pageTop, refreshState } from "../app.js";
import { h, clear, icon, num, eur, ring, toast } from "../ui.js";
import { lineChart } from "./chart.js";

const AGENDA_ICON = { import: "upload", busy: "clock", review: "eye", export: "scissors", post: "post", views: "refresh", quest: "target" };

export function statusPill(st) {
  const ic = { green: "ok", yellow: "alert", red: "octagon", start: "spark" }[st.level];
  return h("div", { class: "status-pill " + st.level, role: "status" }, icon(ic), h("b", {}, st.title), h("span", {}, st.text));
}
export function deltaEl(cur, prev, suffix) {
  if (!prev) return h("span", { class: "delta muted" }, "kein Vergleich");
  const p = (cur - prev) / prev * 100;
  if (Math.abs(p) < 0.5) return h("span", { class: "delta muted" }, "±0 % " + suffix);
  return h("span", { class: "delta " + (p > 0 ? "up" : "down") }, (p > 0 ? "▲ " : "▼ ") + Math.abs(p).toFixed(0) + " %", h("span", { class: "muted" }, " " + suffix));
}
export function achievementsGrid(list) {
  return h("div", { class: "ach" }, list.map(a => h("div", { class: "a" + (a.done ? " done" : "") },
    h("div", { class: "t" }, icon(a.done ? "trophy" : "target"), a.title),
    h("p", {}, a.desc),
    h("div", { class: "bar", title: `${num(a.value)} von ${num(a.target)}` }, h("i", { style: { width: Math.min(100, a.value / a.target * 100) + "%" } })))));
}
export function projectionBlock(d) {
  const p = d.projection;
  if (!p) return h("div", { class: "note box" }, "Sobald du Views bei einem geposteten Clip einträgst, rechne ich hier hoch, was bei deinem Tempo pro Woche, Monat und Jahr herauskommt.");
  return h("div", { class: "col" },
    h("div", { class: "proj" },
      h("div", {}, h("span", {}, "diese Woche"), h("b", {}, eur(p.week))),
      h("div", {}, h("span", {}, "im Monat"), h("b", {}, eur(p.month))),
      h("div", {}, h("span", {}, "im Jahr"), h("b", {}, eur(p.year)))),
    h("div", { class: "note" }, `Bei deinem aktuellen Tempo: ${eur(p.per_day, true)} pro Tag (Schnitt der letzten ${p.basis_days === 1 ? "24 Stunden" : p.basis_days + " Tage"}).`));
}
export function timeSavedBlock(t) {
  if (t.saved_min == null) return h("div", { class: "note box" }, `Von Hand brauchst du laut deiner Angabe ${num(t.manual_min)} Minuten pro Clip. Nach deinem ersten Export messe ich, wie viel die App davon spart.`);
  const saved = Math.max(0, t.saved_min);
  return h("div", { class: "col" },
    h("div", { class: "row" }, h("div", { class: "num" }, num(saved), h("small", {}, " Min. gespart pro Clip"))),
    h("div", { class: "note" }, `Ein Clip kostet dich in der App im Schnitt ${String(t.app_min).replace(".", ",")} Min. (Rechenzeit ${String(t.machine_min).replace(".", ",")} + deine Prüfzeit ${String(t.review_min).replace(".", ",")}), von Hand ${num(t.manual_min)} Min. Gemessen an ${t.clips} ${t.clips === 1 ? "Clip" : "Clips"}.`));
}

export async function render(root) {
  let chart = null;
  async function draw() {
    const d = await api.get("/api/dashboard");
    chart?.destroy();
    const q = d.quest, done = q.target > 0 && q.done >= q.target;
    const today = new Date().toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" });
    const m = d.month, pct = m.goal ? m.earnings / m.goal : 0, pace = m.soll ? m.earnings / m.soll : 1;
    const barCls = !m.goal || d.status.level === "start" ? "" : pace < 0.6 ? "crit" : pace < 0.9 ? "warn" : "good";
    chart = lineChart(d.series, "Einnahmen pro Tag in den letzten 30 Tagen");
    const sum30 = d.series.reduce((s, x) => s + x.earnings, 0);
    const fresh = d.status.level === "start" && !app.state.sample;

    clear(root,
      pageTop("Cockpit", today, statusPill(d.status)),
      h("div", { class: "grid in" },
        h("div", { class: "grid g21" },
          h("section", { class: "panel hud" },
            h("div", { class: "head" }, icon("target"), h("h2", {}, "Tagesquest"), h("span", { class: "right" }, done ? "geschafft" : "läuft")),
            h("div", { class: "quest" },
              ring(q.done, q.target || 1, 148, 11, done ? "good" : "gold", [h("b", {}, q.target ? `${q.done}/${q.target}` : q.done), h("span", {}, "Clips heute")]),
              h("div", { class: "col grow" },
                h("div", {}, h("div", { class: "eyebrow" }, "Auftrag"),
                  h("div", { style: { font: "600 19px var(--display)", marginTop: "6px" } }, q.target ? (done ? `Tagesziel erreicht – ${q.done} Clips gepostet` : `Poste heute ${q.target} Clips`) : "Kein Tagesziel gesetzt"),
                  h("div", { class: "note", style: { marginTop: "4px" } }, q.target ? (done ? "Stark. Alles darüber ist Bonus." : `Noch ${q.target - q.done} bis zum Ziel.`) : h("a", { href: "#/ziele" }, "Ziel festlegen"))),
                h("div", { class: "stat3" },
                  h("div", { class: "stat" }, h("div", { class: "lbl" }, icon("eye"), "Views heute"), h("div", { class: "num" }, num(d.today.views))),
                  h("div", { class: "stat" }, h("div", { class: "lbl" }, icon("euro"), "Einnahmen heute"), h("div", { class: "num" }, eur(d.today.earnings))),
                  h("div", { class: "stat" }, h("div", { class: "lbl" }, icon("flame"), "Serie"), h("div", { class: "num" }, d.streak.current, h("small", {}, d.streak.current === 1 ? " Tag" : " Tage"))))))),
          h("section", { class: "panel" },
            h("div", { class: "head" }, icon("bolt"), h("h2", {}, "Heute steht an")),
            d.agenda.length ? h("div", { class: "agenda col" }, d.agenda.map(a => h("a", { href: a.link },
              h("span", { class: "ico" }, icon(AGENDA_ICON[a.kind] || "check")), h("span", { class: "grow" }, a.text),
              a.count != null ? h("span", { class: "cnt" }, a.count) : null, h("span", { class: "go" }, icon("chevron")))))
              : h("div", { class: "empty" }, icon("ok"), h("b", {}, "Alles erledigt"), "Für heute steht nichts mehr an."),
            fresh ? h("div", { style: { marginTop: "12px" } }, h("button", { class: "btn sm ghost", onclick: async () => { await api.post("/api/sample"); toast("Beispieldaten geladen"); await refreshState(); } }, icon("wand"), "Mit Beispieldaten ansehen")) : null)),

        h("div", { class: "grid g3" },
          h("section", { class: "panel" },
            h("div", { class: "head" }, icon("flag"), h("h2", {}, `Monatsziel ${m.name}`), h("span", { class: "right mono" }, m.goal ? Math.round(pct * 100) + " %" : "")),
            h("div", { class: "num" }, eur(m.earnings), h("small", {}, m.goal ? ` von ${eur(m.goal)}` : "")),
            m.goal ? h("div", { class: "goalbar", style: { marginTop: "14px" } },
              h("div", { class: "bar " + barCls }, h("i", { style: { width: Math.min(100, pct * 100) + "%" } })),
              h("div", { class: "soll", style: { left: Math.min(100, m.soll / m.goal * 100) + "%" } }, h("em", {}, `Soll heute ${eur(m.soll)}`))) : h("div", { class: "note" }, h("a", { href: "#/ziele" }, "Monatsziel festlegen")),
            m.goal && m.start_day > 1 ? h("div", { class: "note" }, `Soll gerechnet ab deinem Start am ${m.start_day}. ${m.name}.`) : null),
          h("section", { class: "panel" },
            h("div", { class: "head" }, icon("chart"), h("h2", {}, "Hochrechnung")),
            projectionBlock(d)),
          h("section", { class: "panel" },
            h("div", { class: "head" }, icon("clock"), h("h2", {}, "Zeitersparnis")),
            timeSavedBlock(d.time_saved))),

        h("div", { class: "grid g21" },
          h("section", { class: "panel" },
            h("div", { class: "head" }, icon("coins"), h("h2", {}, "Einnahmen · letzte 30 Tage"), h("span", { class: "right mono" }, eur(sum30))),
            chart.el),
          h("section", { class: "panel" },
            h("div", { class: "head" }, icon("alert"), h("h2", {}, "Hinweise")),
            h("div", { class: "warnlist" }, d.warnings.length
              ? d.warnings.map(w => h("div", { class: w.level }, icon(w.level === "red" ? "octagon" : "alert"), w.text))
              : h("div", { class: "green" }, icon("ok"), d.status.level === "start" ? "Noch keine Daten – sobald du postest, wache ich über Ziele und Budgets." : "Keine Warnungen. Ziele und Budgets sind im Plan.")),
            h("div", { class: "stat3", style: { marginTop: "14px" } },
              h("div", { class: "stat" }, h("div", { class: "lbl" }, "7 Tage"), h("div", { class: "num", style: { fontSize: "18px" } }, eur(d.week.earnings)), deltaEl(d.week.earnings, d.week.prev_earnings, "")),
              h("div", { class: "stat" }, h("div", { class: "lbl" }, "Views"), h("div", { class: "num", style: { fontSize: "18px" } }, num(d.week.views)), deltaEl(d.week.views, d.week.prev_views, "")),
              h("div", { class: "stat" }, h("div", { class: "lbl" }, "Clips"), h("div", { class: "num", style: { fontSize: "18px" } }, d.week.clips), deltaEl(d.week.clips, d.week.prev_clips, ""))))),

        h("section", { class: "panel" },
          h("div", { class: "head" }, icon("trophy"), h("h2", {}, "Erfolge"), h("span", { class: "right" }, `${d.achievements.filter(a => a.done).length} von ${d.achievements.length} freigeschaltet`)),
          achievementsGrid(d.achievements))));
  }
  await draw();
  return { cleanup: () => chart?.destroy(), onState: (_, finished) => { if (finished.length) draw(); } };
}
