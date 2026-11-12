// Kampagnen & Einnahmen: Kampagnen anlegen, Posts und Views eintragen, Einnahmen je Clip, Kampagne, Tag, Monat.
import { api } from "../api.js";
import { pageTop, refreshState, confirmBox } from "../app.js";
import { h, clear, icon, toast, num, eur, modal, field, select, dateDE, dayShort, todayISO, PLATFORMS } from "../ui.js";
import { postDialog } from "./postdialog.js";

function campaignDialog(c, onDone) {
  const name = h("input", { type: "text", value: c?.name || "", id: "camp-name", placeholder: "z. B. Streamer XY – Highlights" });
  const platform = select([{ value: "", label: "Alle Plattformen" }, ...PLATFORMS.slice(0, 3).map(p => ({ value: p, label: p }))], c?.platform || "", { id: "camp-platform" });
  const rate = h("input", { type: "number", min: 0, step: 0.05, value: c?.rate_per_1000 ?? 1, id: "camp-rate" });
  const budget = h("input", { type: "number", min: 0, step: 10, value: c?.budget ?? 0, id: "camp-budget" });
  const rules = h("textarea", { id: "camp-rules", placeholder: "z. B. Pflicht-Hashtag #xy, Kanal erwähnen, keine Musik, 20–60 Sekunden" }, c?.rules || "");
  modal(c ? "Kampagne bearbeiten" : "Kampagne anlegen", "Daraus berechne ich deine Einnahmen pro 1.000 Views.",
    h("div", { class: "form" }, field("Name", name),
      h("div", { class: "two" }, field("Plattform", platform), field("Bezahlung pro 1.000 Views (€)", rate)),
      field("Budget der Kampagne (€)", budget, "0 = kein Limit. Ist das Budget aufgebraucht, zähle ich keine weiteren Einnahmen."),
      field("Regeln", rules, "Die Regeln beachtet die KI beim Schreiben von Titel, Beschreibung und Hashtags.")),
    [{ label: "Abbrechen", class: "ghost" }, { label: c ? "Speichern" : "Anlegen", class: "primary", icon: "check", onclick: async () => {
      const body = { name: name.value, platform: platform.value, rate_per_1000: +rate.value || 0, budget: +budget.value || 0, rules: rules.value };
      try { c ? await api.patch(`/api/campaigns/${c.id}`, body) : await api.post("/api/campaigns", body); toast(c ? "Kampagne gespeichert" : "Kampagne angelegt"); await onDone(); }
      catch (e) { toast(e.message, "err"); return false; }
    } }]);
}

export async function render(root) {
  const body = h("div", { class: "grid in" });
  let e = null;

  async function load() {
    e = await api.get("/api/earnings");
    const pipe = await api.get("/api/pipeline");
    const postable = [...pipe.done, ...pipe.posted];
    const month = todayISO().slice(0, 7), today = todayISO();
    const mEarn = e.months.find(m => m.month === month)?.earnings || 0;
    const tEarn = e.days.find(d => d.day === today)?.earnings || 0;
    const views = e.posts.reduce((s, p) => s + (p.views || 0), 0);

    clear(body,
      h("div", { class: "grid g4" },
        tile("coins", "Einnahmen gesamt", eur(e.total)), tile("flag", "Diesen Monat", eur(mEarn)), tile("euro", "Heute", eur(tEarn)), tile("eye", "Views gesamt", num(views))),

      h("section", { class: "panel" },
        h("div", { class: "head" }, icon("flag"), h("h2", {}, "Kampagnen"),
          h("button", { class: "btn sm primary right", id: "add-campaign", onclick: () => campaignDialog(null, done) }, icon("plus"), "Kampagne anlegen")),
        e.campaigns.length ? h("div", { class: "grid g3" }, e.campaigns.map(c => {
          const used = c.used, cls = used == null ? "" : used >= 1 ? "crit" : used >= 0.85 ? "warn" : "good";
          return h("div", { class: "stat", style: { opacity: c.active ? 1 : .55 }, "data-campaign": c.id },
            h("div", { class: "spread" }, h("b", { class: "ellipsis", style: { fontSize: "14.5px" } }, c.name),
              h("div", { class: "row", style: { gap: "2px" } },
                h("button", { class: "btn sm icon ghost", title: "Bearbeiten", "aria-label": `${c.name} bearbeiten`, onclick: () => campaignDialog(c, done) }, icon("sliders")),
                h("button", { class: "btn sm icon ghost", title: "Löschen", "aria-label": `${c.name} löschen`, onclick: () => confirmBox("Kampagne löschen?", `„${c.name}“ wird gelöscht. Posts bleiben erhalten, zählen aber keine Einnahmen mehr.`, "Löschen",
                  async () => { await api.del(`/api/campaigns/${c.id}`); toast("Kampagne gelöscht"); await done(); }, true) }, icon("trash")))),
            h("div", { class: "row wrap", style: { margin: "6px 0 10px", gap: "5px" } },
              c.is_sample ? h("span", { class: "chip warn" }, "Beispiel") : null,
              h("span", { class: "chip" }, c.platform || "Alle Plattformen"),
              h("span", { class: "chip accent mono" }, `${eur(c.rate_per_1000, true)} / 1.000`),
              h("span", { class: "chip" }, `${c.posts} ${c.posts === 1 ? "Post" : "Posts"}`),
              c.active ? null : h("span", { class: "chip" }, "pausiert")),
            h("div", { class: "num", style: { fontSize: "22px" } }, eur(c.earned, true), c.budget ? h("small", {}, ` von ${eur(c.budget)}`) : h("small", {}, " · kein Budget-Limit")),
            c.budget ? h("div", { class: "bar " + cls, style: { marginTop: "9px" } }, h("i", { style: { width: Math.min(100, used * 100) + "%" } })) : null,
            c.rules ? h("div", { class: "note", style: { marginTop: "9px" } }, c.rules) : null,
            h("label", { class: "check", style: { marginTop: "9px" } }, h("input", { type: "checkbox", checked: !!c.active, onchange: async ev => { await api.patch(`/api/campaigns/${c.id}`, { active: ev.target.checked }); await done(); } }), h("span", {}, "Kampagne läuft")));
        })) : h("div", { class: "empty" }, icon("flag"), h("b", {}, "Noch keine Kampagne"), "Lege eine Kampagne mit Bezahlung pro 1.000 Views an. Danach kannst du geposteten Clips Views zuordnen.")),

      h("section", { class: "panel" },
        h("div", { class: "head" }, icon("post"), h("h2", {}, "Gepostete Clips"),
          h("button", { class: "btn sm right", id: "add-post", disabled: !postable.length, title: postable.length ? "" : "Erst einen Clip exportieren", onclick: () => {
            const pick = select(postable.map(c => ({ value: c.id, label: `${c.title || "Clip"} · ${c.project_title}` })), postable[0].id, { id: "pick-clip" });
            modal("Welcher Clip wurde gepostet?", "Ein Clip kann auf mehreren Plattformen stehen – trage jeden Post einzeln ein.", field("Clip", pick),
              [{ label: "Abbrechen", class: "ghost" }, { label: "Weiter", class: "primary", onclick: () => { const c = postable.find(x => x.id === +pick.value); setTimeout(() => postDialog(c, e.campaigns, done), 0); } }]);
          } }, icon("plus"), "Post eintragen")),
        e.posts.length ? h("div", { class: "scroll-x" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Clip"), h("th", {}, "Plattform"), h("th", {}, "Kampagne"), h("th", {}, "Gepostet"), h("th", { class: "n" }, "Views"), h("th", { class: "n" }, "Einnahmen"), h("th", {}, ""))),
          h("tbody", {}, e.posts.map(p => {
            const inp = h("input", { type: "number", min: 0, step: 1, value: p.views, style: { width: "120px", height: "32px", textAlign: "right" }, "aria-label": `Views für ${p.clip_title}`, "data-post": p.id,
              onkeydown: ev => { if (ev.key === "Enter") ev.target.blur(); },
              onchange: async ev => { try { await api.patch(`/api/posts/${p.id}`, { views: +ev.target.value || 0 }); toast("Views aktualisiert"); await done(); } catch (err) { toast(err.message, "err"); } } });
            return h("tr", {},
              h("td", {}, p.url ? h("a", { href: p.url, target: "_blank", rel: "noopener" }, p.clip_title || "Clip") : (p.clip_title || "Clip"), p.is_sample ? h("span", { class: "chip warn", style: { marginLeft: "6px" } }, "Beispiel") : null),
              h("td", {}, p.platform), h("td", {}, p.campaign_name || h("span", { class: "muted" }, "–")), h("td", { class: "mono" }, dateDE(p.posted_at)),
              h("td", { class: "n" }, inp), h("td", { class: "n" }, eur(p.earned, true)),
              h("td", {}, h("button", { class: "btn sm icon ghost", title: "Post löschen", "aria-label": "Post löschen", onclick: () => confirmBox("Post löschen?", "Der Eintrag und seine Views werden entfernt.", "Löschen", async () => { await api.del(`/api/posts/${p.id}`); await done(); }, true) }, icon("trash"))));
          }))))
          : h("div", { class: "empty" }, icon("post"), h("b", {}, "Noch nichts gepostet"), "Sobald du einen fertigen Clip postest, trägst du hier Link und Views ein."),
        e.posts.length ? h("div", { class: "note", style: { marginTop: "10px" } }, "Trag die aktuelle Gesamtzahl der Views ein. Der Zuwachs zählt als Einnahme für den Tag, an dem du ihn einträgst.") : null),

      h("div", { class: "grid g2" },
        h("section", { class: "panel" }, h("div", { class: "head" }, icon("chart"), h("h2", {}, "Einnahmen pro Tag")),
          e.days.length ? h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Tag"), h("th", { class: "n" }, "Views"), h("th", { class: "n" }, "Einnahmen"))),
            h("tbody", {}, e.days.slice(0, 14).map(d => h("tr", {}, h("td", { class: "mono" }, dayShort(d.day) + (d.day === today ? " · heute" : "")), h("td", { class: "n" }, num(d.views)), h("td", { class: "n" }, eur(d.earnings, true))))))
            : h("div", { class: "note" }, "Noch keine Einnahmen erfasst.")),
        h("section", { class: "panel" }, h("div", { class: "head" }, icon("coins"), h("h2", {}, "Einnahmen pro Monat")),
          e.months.length ? h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Monat"), h("th", { class: "n" }, "Einnahmen"))),
            h("tbody", {}, e.months.map(m => h("tr", {}, h("td", {}, new Date(m.month + "-15").toLocaleDateString("de-DE", { month: "long", year: "numeric" })), h("td", { class: "n" }, eur(m.earnings, true))))))
            : h("div", { class: "note" }, "Noch keine Einnahmen erfasst."))));
  }
  const tile = (ic, label, value) => h("div", { class: "panel", style: { padding: "14px 16px" } }, h("div", { class: "stat", style: { border: 0, background: "none", padding: 0 } }, h("div", { class: "lbl" }, icon(ic), label), h("div", { class: "num" }, value)));
  async function done() { await refreshState(); await load(); }

  clear(root, pageTop("Einnahmen", "Kampagnen, Posts und Views"), body);
  await load();
  return {};
}
