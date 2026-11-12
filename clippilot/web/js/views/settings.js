// Einstellungen: KI-Key, Transkription, Clip-Vorgaben, Beispieldaten.
import { api } from "../api.js";
import { app, pageTop, refreshState } from "../app.js";
import { h, clear, icon, toast, field, select } from "../ui.js";

export async function render(root) {
  const body = h("div", { class: "grid in" });
  async function load() {
    const s = await api.get("/api/settings");
    const key = h("input", { type: "password", id: "set-key", autocomplete: "off", placeholder: s.has_api_key ? `Gespeichert (endet auf ${s.api_key_hint || "…"}) – zum Ändern neuen Key eingeben` : "sk-ant-…" });
    const testOut = h("div", { class: "note", id: "key-result" });
    const model = select(app.meta.ai_models.map(m => ({ value: m.id, label: m.label })), s.ai_model, { id: "set-model" });
    const whisper = select(app.meta.whisper_models.map(m => ({ value: m.id, label: m.label })), s.whisper_model, { id: "set-whisper" });
    const lang = select([{ value: "auto", label: "Automatisch erkennen" }, { value: "de", label: "Deutsch" }, { value: "en", label: "Englisch" }], s.language, { id: "set-lang" });
    const num = (id, v, min, max, step = 1) => h("input", { type: "number", id, value: v, min, max, step });
    const minS = num("set-min", s.clip_min_s, 5, 170), maxS = num("set-max", s.clip_max_s, 10, 180), count = num("set-count", s.num_suggestions, 1, 30), hookS = num("set-hook", s.hook_seconds, 0, 10, 0.5);
    const tpl = select(app.meta.templates.map(t => ({ value: t.id, label: `${t.label} – ${t.desc}` })), s.caption_template, { id: "set-tpl" });
    const layout = select([{ value: "auto", label: "Automatisch (Gesicht folgen, sonst ganzes Bild)" }, { value: "face", label: "Gesicht folgen (Zoom)" }, { value: "blur", label: "Ganzes Bild, unscharfer Hintergrund" }], s.layout, { id: "set-layout" });
    const saveBtn = (id, fn) => h("button", { class: "btn primary", id, onclick: async e => { const b = e.currentTarget; b.disabled = true; try { await fn(); toast("Gespeichert"); await refreshState(); await load(); } catch (err) { toast(err.message, "err"); } finally { b.disabled = false; } } }, icon("check"), "Speichern");

    clear(body,
      h("div", { class: "grid g2" },
        h("section", { class: "panel hud" },
          h("div", { class: "head" }, icon("spark"), h("h2", {}, "KI für Highlights und Texte"), h("span", { class: "right" }, h("span", { class: "chip " + (s.has_api_key ? "good" : "warn") }, s.has_api_key ? "Key gespeichert" : "kein Key"))),
          h("div", { class: "form" },
            h("div", { class: "note box" }, h("b", { class: "dim" }, "Welcher Key? "), "Ein API-Key von Anthropic (für Claude). So bekommst du ihn:",
              h("ol", { class: "steps" }, h("li", {}, "Auf ", h("a", { href: "https://console.anthropic.com", target: "_blank", rel: "noopener" }, "console.anthropic.com"), " anmelden."), h("li", {}, "Unter „API Keys“ einen neuen Key erstellen. Er beginnt mit sk-ant-."), h("li", {}, "Guthaben aufladen, hier einfügen, speichern."))),
            field("Anthropic-API-Key", h("div", { class: "keyrow" }, key,
              h("button", { class: "btn", id: "key-test", onclick: async e => { const b = e.currentTarget; b.disabled = true; testOut.textContent = "Prüfe …";
                try { if (key.value.trim()) await api.post("/api/settings", { anthropic_api_key: key.value.trim() }); const r = await api.post("/api/settings/test-key"); testOut.textContent = r.message; testOut.style.color = r.ok ? "var(--good)" : "var(--crit)"; await refreshState(); }
                catch (err) { testOut.textContent = err.message; } finally { b.disabled = false; } } }, "Testen")),
              "Der Key wird nur auf deinem Rechner gespeichert (Ordner data) und nie im Programmcode."),
            testOut,
            field("KI-Modell", model, "Kosten fallen pro Analyse bei Anthropic an. Opus liefert die besten Vorschläge, Haiku ist am günstigsten."),
            h("div", { class: "row" },
              saveBtn("save-ai", async () => { const p = { ai_model: model.value }; if (key.value.trim()) p.anthropic_api_key = key.value.trim(); await api.post("/api/settings", p); }),
              s.has_api_key ? h("button", { class: "btn danger", onclick: async () => { await api.post("/api/settings", { anthropic_api_key: "" }); toast("Key entfernt"); await refreshState(); await load(); } }, icon("trash"), "Key entfernen") : null),
            h("div", { class: "note" }, "Ohne Key funktioniert alles weiter. Highlights und Texte kommen dann aus einer einfacheren lokalen Analyse und sind entsprechend gekennzeichnet."))),

        h("section", { class: "panel" },
          h("div", { class: "head" }, icon("mic"), h("h2", {}, "Transkription"), h("span", { class: "right" }, h("span", { class: "chip" }, "läuft auf: " + app.meta.device))),
          h("div", { class: "form" },
            field("Sprachmodell (Whisper)", whisper, "Läuft komplett auf deinem Rechner, kein Key nötig. Das Modell wird beim ersten Mal heruntergeladen."),
            field("Sprache der Videos", lang),
            h("div", {}, saveBtn("save-tr", () => api.post("/api/settings", { whisper_model: whisper.value, language: lang.value })))))),

      h("div", { class: "grid g2" },
        h("section", { class: "panel" },
          h("div", { class: "head" }, icon("scissors"), h("h2", {}, "Vorgaben für neue Clips")),
          h("div", { class: "form" },
            h("div", { class: "two" }, field("Mindestlänge (Sekunden)", minS), field("Höchstlänge (Sekunden)", maxS)),
            h("div", { class: "two" }, field("Vorschläge pro Video", count), field("Hook-Text einblenden (Sekunden)", hookS)),
            field("Untertitel-Vorlage", tpl), field("Bildausschnitt", layout),
            h("div", {}, saveBtn("save-clip", () => api.post("/api/settings", { clip_min_s: +minS.value, clip_max_s: +maxS.value, num_suggestions: +count.value, hook_seconds: +hookS.value, caption_template: tpl.value, layout: layout.value }))))),
        h("section", { class: "panel" },
          h("div", { class: "head" }, icon("folder"), h("h2", {}, "Daten")),
          h("div", { class: "col" },
            h("div", { class: "note" }, "Videos, Clips, Einstellungen und die Datenbank liegen im Ordner ", h("b", { class: "dim" }, "data"), " neben der Start-Datei. Nichts davon wird hochgeladen – außer dem Transkript, wenn du die KI mit einem Key nutzt."),
            app.state.sample
              ? h("button", { class: "btn danger", id: "sample-clear", onclick: async () => { await api.del("/api/sample"); toast("Beispieldaten gelöscht"); await refreshState(); await load(); } }, icon("trash"), "Beispieldaten löschen")
              : h("button", { class: "btn", id: "sample-load", onclick: async () => { await api.post("/api/sample"); toast("Beispieldaten geladen"); await refreshState(); await load(); } }, icon("wand"), "Beispieldaten laden"),
            h("div", { class: "note" }, "Beispieldaten sind überall als „Beispiel“ markiert und lassen sich mit einem Klick wieder entfernen. Deine echten Daten bleiben unberührt.")))));
  }
  clear(root, pageTop("Einstellungen"), body);
  await load();
  return {};
}
