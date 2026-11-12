// Grundgerüst: Seitenleiste, Seitenwechsel, Status-Abfrage, Mini-Fenster.
import { api } from "./api.js";
import { h, clear, icon, num, eur, toast, confirmBox } from "./ui.js";

const ROUTES = {
  cockpit: { label: "Cockpit", icon: "cockpit", load: () => import("./views/cockpit.js") },
  projekte: { label: "Videos", icon: "film", load: () => import("./views/projects.js") },
  projekt: { parent: "projekte", load: () => import("./views/review.js") },
  pipeline: { label: "Pipeline", icon: "kanban", load: () => import("./views/pipeline.js") },
  kampagnen: { label: "Einnahmen", icon: "coins", load: () => import("./views/campaigns.js") },
  ziele: { label: "Ziele", icon: "target", load: () => import("./views/goals.js") },
  einstellungen: { label: "Einstellungen", icon: "sliders", load: () => import("./views/settings.js") },
};

export const app = { meta: null, state: { jobs: [], hud: null, sample: false, has_api_key: false }, view: null };
let cleanup = null, pollTimer = null, lastActive = new Set(), navEl, mainEl, hudEl;

function parseHash() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  return { name: ROUTES[parts[0]] ? parts[0] : "cockpit", args: parts.slice(1) };
}

async function route() {
  const { name, args } = parseHash();
  if (name === "mini") return;
  if (cleanup) { try { cleanup(); } catch { /* */ } cleanup = null; }
  document.querySelectorAll(".modal-back").forEach(m => m.remove());      // offene Dialoge gehören zur alten Seite
  app.view = null;
  const active = ROUTES[name].parent || name;
  for (const a of navEl.querySelectorAll("a")) a.classList.toggle("on", a.dataset.route === active);
  // Auf der Review-Seite klappt das Mini-Fenster von selbst ein, damit es nichts verdeckt (außer du hast es anders eingestellt).
  const pref = hudPref();
  if (hudEl.isConnected && hudEl.ownerDocument === document) hudEl.classList.toggle("min", pref === "1" || (pref == null && name === "projekt"));
  try {
    const mod = await ROUTES[name].load();
    const root = h("div", { class: "view" });
    clear(mainEl, banner(), root);
    const res = await mod.render(root, args);
    cleanup = res?.cleanup || null;
    app.view = res || null;
    renderJobs(app.state.jobs.filter(j => j.status === "queued" || j.status === "running"));
    window.scrollTo(0, 0);
  } catch (e) {
    clear(mainEl, h("div", { class: "panel empty" }, icon("octagon"), h("b", {}, "Diese Seite konnte nicht geladen werden"), e.message));
  }
}

function banner() {
  if (!app.state.sample) return null;
  return h("div", { class: "banner", id: "sample-banner" }, icon("alert"),
    h("div", { class: "grow" }, h("b", {}, "Beispieldaten aktiv. "), "Die Zahlen und Clips mit „Beispiel“ sind erfunden und dienen nur zum Ausprobieren."),
    h("button", { class: "btn sm", onclick: async () => { await api.del("/api/sample"); toast("Beispieldaten gelöscht"); await poll(); route(); } }, icon("trash"), "Beispieldaten löschen"));
}

// ---------- Status-Abfrage (laufende Aufgaben + Zahlen fürs Mini-Fenster) ----------
async function poll() {
  clearTimeout(pollTimer);
  try {
    const st = await api.get("/api/state");
    const hadSample = app.state.sample;
    app.state = st;
    const active = new Set(st.jobs.filter(j => j.status === "queued" || j.status === "running").map(j => j.id));
    const finished = st.jobs.filter(j => lastActive.has(j.id) && !active.has(j.id));
    for (const j of finished) {
      if (j.status === "error") toast(`${j.label} fehlgeschlagen: ${j.error}`, "err");
      else if (j.kind === "export") toast(`Clip „${j.clip_title || ""}“ ist fertig exportiert`);
      else if (j.kind === "process" || j.kind === "download" || j.kind === "analyze") toast(`„${j.project_title || "Video"}“ ist bereit zum Prüfen`);
    }
    lastActive = active;
    renderJobs(st.jobs.filter(j => active.has(j.id)));
    renderHud(st.hud);
    app.view?.onState?.(st, finished);
    if (hadSample !== st.sample && !document.querySelector(".modal-back")) route();
    pollTimer = setTimeout(poll, active.size ? 1200 : 4000);
  } catch {
    pollTimer = setTimeout(poll, 4000);
  }
}
export const refreshState = poll;

function renderJobs(active) {
  const box = document.getElementById("jobs-ind");
  if (!box) return;
  if (!active.length) { box.classList.add("hide"); return; }
  const j = active.find(x => x.status === "running") || active[0];
  box.classList.remove("hide");
  clear(box, h("span", { class: "spin" }),
    h("span", { class: "ellipsis" }, `${j.label}${active.length > 1 ? ` (+${active.length - 1})` : ""} · ${Math.round((j.progress || 0) * 100)} %`));
  box.title = j.message || "";
}

// ---------- Mini-Fenster ----------
function hudPref() { try { return localStorage.getItem("hud-min"); } catch { return null; } }
function buildHud() {
  const el = h("div", { id: "hud", role: "complementary", "aria-label": "Mini-Fenster: heute" },
    h("div", { class: "hd" }, h("span", { class: "dot" }), h("b", {}, "HEUTE"), h("span", { class: "line", id: "hud-line" }),
      h("button", { class: "pop", title: "Als eigenes Fenster ablösen (bleibt im Vordergrund)", "aria-label": "Mini-Fenster ablösen", onclick: popOut }, icon("pip")),
      h("button", { class: "tog", title: "Ein- oder ausklappen", "aria-label": "Mini-Fenster ein- oder ausklappen", onclick: () => { el.classList.toggle("min"); try { localStorage.setItem("hud-min", el.classList.contains("min") ? "1" : "0"); } catch { /* */ } } }, icon("minus"))),
    h("div", { class: "vals" },
      h("div", {}, h("b", { id: "hud-clips" }, "–"), h("span", {}, "Clips")),
      h("div", {}, h("b", { id: "hud-views" }, "–"), h("span", {}, "Views")),
      h("div", {}, h("b", { id: "hud-eur" }, "–"), h("span", {}, "Einnahmen"))),
    h("div", { class: "bar good" }, h("i", { id: "hud-bar", style: { width: "0%" } })),
    h("div", { class: "goal" }, h("span", {}, "Tagesziel"), h("span", { id: "hud-goal" }, "")));
  if (hudPref() === "1") el.classList.add("min");
  return el;
}
function renderHud(d) {
  if (!d || !hudEl) return;
  const q = id => hudEl.querySelector("#" + id);
  q("hud-clips").textContent = d.goal ? `${d.clips}/${d.goal}` : d.clips;
  q("hud-views").textContent = num(d.views);
  q("hud-eur").textContent = eur(d.earnings);
  q("hud-line").textContent = `${d.goal ? `${d.clips}/${d.goal}` : d.clips} Clips · ${num(d.views)} Views · ${eur(d.earnings)}`;
  q("hud-bar").style.width = (d.goal ? Math.min(100, d.clips / d.goal * 100) : 0) + "%";
  q("hud-goal").textContent = !d.goal ? "kein Ziel gesetzt" : d.clips >= d.goal ? "geschafft" : `noch ${d.goal - d.clips}`;
}
async function popOut() {
  // Chrome/Edge: echtes Mini-Fenster, das über anderen Programmen sichtbar bleibt.
  if ("documentPictureInPicture" in window) {
    try {
      const w = await window.documentPictureInPicture.requestWindow({ width: 290, height: 150 });
      w.document.head.append(h("link", { rel: "stylesheet", href: location.origin + "/static/css/app.css" }));
      w.document.body.className = "mini";
      w.document.title = "ClipPilot";
      const home = hudEl.parentNode;
      hudEl.classList.remove("min");
      w.document.body.append(hudEl);
      w.addEventListener("pagehide", () => home.append(hudEl));
      return;
    } catch { /* weiter mit normalem Fenster */ }
  }
  const w = window.open("/#/mini", "clippilot-mini", "width=300,height=170");
  if (!w) toast("Dein Browser hat das Fenster blockiert. Bitte Pop-ups für ClipPilot erlauben.", "err");
}

// ---------- Start ----------
async function start() {
  const root = document.getElementById("app");
  if (location.hash.replace(/^#\/?/, "") === "mini") {       // abgelöstes Mini-Fenster (Ersatz ohne Chrome/Edge)
    document.body.className = "mini";
    hudEl = buildHud();
    clear(document.body, hudEl);
    poll();
    return;
  }
  try { app.meta = await api.get("/api/meta"); } catch (e) {
    clear(root, h("div", { class: "panel empty", style: { margin: "40px" } }, icon("octagon"), h("b", {}, "Keine Verbindung"), e.message));
    return;
  }
  navEl = h("nav", { class: "nav", "aria-label": "Hauptmenü" }, Object.entries(ROUTES).filter(([, r]) => r.label).map(([k, r]) =>
    h("a", { href: "#/" + k, "data-route": k }, icon(r.icon), h("span", {}, r.label))));
  mainEl = h("div", { id: "main" });
  hudEl = buildHud();
  clear(root,
    h("aside", { class: "side" },
      h("div", { class: "brand" }, h("div", { class: "mark" }, icon("play")), h("div", {}, h("b", {}, "ClipPilot"), h("span", {}, "CLIP STUDIO"))),
      navEl,
      h("div", { class: "side-foot" }, `Version ${app.meta.version}`, h("br"), "Alles bleibt auf deinem Rechner.")),
    h("main", {}, mainEl), hudEl);
  window.addEventListener("hashchange", route);
  await poll();
  await route();
}

// Kopfzeile, die jede Seite benutzt
export function pageTop(title, sub, ...right) {
  return h("div", { class: "top" }, h("div", { style: { marginRight: "auto" } }, h("h1", {}, title), sub ? h("div", { class: "sub" }, sub) : null),
    h("div", { class: "jobs-ind hide", id: "jobs-ind" }), ...right);
}
export { confirmBox };
start();
