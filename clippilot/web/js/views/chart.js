// Liniendiagramm für Einnahmen (eine Reihe, mit Fadenkreuz und Tastatur-Bedienung).
import { h, eur } from "../ui.js";

function niceStep(raw) {
  const p = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1e-9)))), f = raw / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
}

export function lineChart(series, label) {
  const wrap = h("div", { class: "chart", tabindex: "0", role: "img", "aria-label": label });
  const box = h("div", { style: { position: "absolute", inset: "0" } });
  const tip = h("div", { class: "tip hide" });
  wrap.append(box, tip);
  let geo = null;

  function draw() {
    const W = Math.max(260, wrap.clientWidth), H = Math.max(160, wrap.clientHeight);
    const vals = series.map(s => s.earnings), n = vals.length;
    const max = Math.max(1, ...vals);
    const step = niceStep(max / 3.5), yMax = Math.ceil(max * 1.05 / step) * step;
    const axis = v => step >= 1 ? Math.round(v).toLocaleString("de-DE") + "\u00A0€" : eur(v, true);   // eine Schreibweise für die ganze Achse
    const m = { t: 12, r: 16, b: 24, l: 16 + axis(yMax).length * 6.4 };
    const x = i => m.l + i * (W - m.l - m.r) / Math.max(1, n - 1);
    const y = v => m.t + (1 - v / yMax) * (H - m.t - m.b);
    const path = vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
    let s = `<svg viewBox="0 0 ${W} ${H}"><defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#4fd8ff" stop-opacity=".28"/><stop offset="1" stop-color="#4fd8ff" stop-opacity="0"/></linearGradient></defs>`;
    for (let t = 0; t <= yMax + 1e-9; t += step)
      s += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}" stroke="${t ? "rgba(124,200,255,.09)" : "rgba(124,200,255,.25)"}"/>
            <text x="${m.l - 8}" y="${y(t) + 3.5}" text-anchor="end">${axis(t)}</text>`;
    for (let i = n - 1; i >= 0; i -= 7)
      s += `<text x="${x(i)}" y="${H - 6}" text-anchor="${i === n - 1 ? "end" : "middle"}">${i === n - 1 ? "heute" : new Date(series[i].day + "T12:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}</text>`;
    s += `<path d="${path} L${x(n - 1)} ${y(0)} L${x(0)} ${y(0)} Z" fill="url(#cg)"/>
      <path d="${path}" fill="none" stroke="#4fd8ff" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" style="filter:drop-shadow(0 0 5px rgba(79,216,255,.55))"/>
      <circle cx="${x(n - 1)}" cy="${y(vals[n - 1])}" r="4.5" fill="#4fd8ff" stroke="#0d131d" stroke-width="2"/>
      <line class="cx" y1="${m.t}" y2="${y(0)}" stroke="rgba(233,241,248,.5)" visibility="hidden"/>
      <circle class="cd" r="5" fill="#4fd8ff" stroke="#0d131d" stroke-width="2" visibility="hidden"/></svg>`;
    box.innerHTML = s;                       // nur selbst berechnete Zahlen
    geo = { x, y, n, m, W, vals };
  }
  function show(i) {
    if (!geo) return;
    i = Math.max(0, Math.min(geo.n - 1, i)); geo.i = i;
    const px = geo.x(i), py = geo.y(geo.vals[i]);
    const cx = box.querySelector(".cx"), cd = box.querySelector(".cd");
    cx.setAttribute("x1", px); cx.setAttribute("x2", px); cx.setAttribute("visibility", "visible");
    cd.setAttribute("cx", px); cd.setAttribute("cy", py); cd.setAttribute("visibility", "visible");
    tip.replaceChildren(h("b", {}, eur(geo.vals[i], true)),
      h("span", {}, new Date(series[i].day + "T12:00").toLocaleDateString("de-DE", { weekday: "short", day: "numeric", month: "long" }) + ` · ${series[i].views.toLocaleString("de-DE")} Views`));
    tip.classList.remove("hide");
    const half = tip.offsetWidth / 2;
    tip.style.left = Math.max(half, Math.min(geo.W - half, px)) + "px";
    tip.style.top = Math.max(tip.offsetHeight + 2, py - 12) + "px";
  }
  function hide() { tip.classList.add("hide"); box.querySelectorAll(".cx,.cd").forEach(e => e.setAttribute("visibility", "hidden")); }
  wrap.addEventListener("pointermove", e => { if (geo) show(Math.round((e.clientX - wrap.getBoundingClientRect().left - geo.m.l) / ((geo.W - geo.m.l - geo.m.r) / Math.max(1, geo.n - 1)))); });
  wrap.addEventListener("pointerleave", hide);
  wrap.addEventListener("focus", () => geo && show(geo.n - 1));
  wrap.addEventListener("blur", hide);
  wrap.addEventListener("keydown", e => { if (!geo || !["ArrowLeft", "ArrowRight"].includes(e.key)) return; e.preventDefault(); show((geo.i ?? geo.n - 1) + (e.key === "ArrowLeft" ? -1 : 1)); });
  const ro = new ResizeObserver(draw);
  ro.observe(wrap);
  return { el: wrap, destroy: () => ro.disconnect() };
}
