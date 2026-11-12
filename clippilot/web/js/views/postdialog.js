// Dialog: wo wurde der Clip gepostet? (Link, Plattform, Kampagne, Views)
import { api } from "../api.js";
import { h, modal, field, select, toast, todayISO, PLATFORMS } from "../ui.js";

export function postDialog(clip, campaigns, onDone) {
  const camp = campaigns.find(k => k.id === clip.campaign_id);
  const guess = PLATFORMS.find(p => camp?.platform && p.toLowerCase().startsWith(camp.platform.toLowerCase().split(" ")[0])) || PLATFORMS[0];
  const platform = select(PLATFORMS.map(p => ({ value: p, label: p })), guess, { id: "post-platform" });
  const campaign = select([{ value: "", label: "Keine Kampagne (keine Einnahmen)" }, ...campaigns.map(k => ({ value: k.id, label: `${k.name} · ${String(k.rate_per_1000).replace(".", ",")} € pro 1.000` }))], clip.campaign_id ?? "", { id: "post-campaign" });
  const url = h("input", { type: "url", placeholder: "https://…", id: "post-url" });
  const date = h("input", { type: "date", value: todayISO(), max: todayISO(), id: "post-date" });
  const views = h("input", { type: "number", min: 0, step: 1, value: 0, id: "post-views" });
  modal("Clip als gepostet eintragen", `„${clip.title || "Clip"}“`,
    h("div", { class: "form" },
      h("div", { class: "two" }, field("Plattform", platform), field("Gepostet am", date)),
      field("Kampagne", campaign),
      field("Link zum Post", url, "Optional – so findest du den Post später wieder."),
      field("Views bis jetzt", views, "Die Views trägst du später unter „Einnahmen“ nach. Daraus berechne ich die Einnahmen.")),
    [{ label: "Abbrechen", class: "ghost" }, { label: "Eintragen", class: "primary", icon: "check", onclick: async () => {
      try {
        await api.post("/api/posts", { clip_id: clip.id, platform: platform.value, campaign_id: campaign.value ? +campaign.value : null, url: url.value, posted_at: date.value, views: +views.value || 0 });
        toast("Post eingetragen"); await onDone?.();
      } catch (e) { toast(e.message, "err"); return false; }
    } }]);
}
