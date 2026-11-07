// Shared helpers for all sections. Teammates: put section code in js/sectionN.js.
window.App = (() => {
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const groupColor = (g) => css(`--g-${g}`);

  const fmt = {
    int: (v) => (v == null ? "–" : Math.round(v).toLocaleString("en-GB")),
    dec: (v, d = 2) => (v == null ? "–" : Number(v).toFixed(d)),
    pct: (v) => (v == null ? "–" : `${Math.round(v * 100)}%`),
  };

  async function loadJSON(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    return r.json();
  }

  // Tooltip: rows = [[label, value], ...]
  const tip = document.getElementById("tooltip");
  function showTip(evt, title, rows) {
    tip.innerHTML =
      `<div class="t-title">${title}</div>` +
      rows.map(([k, v]) => `<div class="t-row"><span>${k}</span><b>${v}</b></div>`).join("");
    tip.hidden = false;
    moveTip(evt);
  }
  function moveTip(evt) {
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + w > innerWidth - 8) x = evt.clientX - w - pad;
    if (y + h > innerHeight - 8) y = evt.clientY - h - pad;
    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
  }
  const hideTip = () => (tip.hidden = true);

  // Highlight the nav link for the section in view.
  const links = [...document.querySelectorAll(".nav a")];
  const obs = new IntersectionObserver(
    (entries) =>
      entries.forEach((e) => {
        if (e.isIntersecting)
          links.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#${e.target.id}`));
      }),
    { rootMargin: "-40% 0px -55% 0px" }
  );
  document.querySelectorAll("section[id]").forEach((s) => obs.observe(s));

  // Re-render hooks for theme changes (colours are CSS tokens).
  const themeListeners = [];
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => themeListeners.forEach((f) => f()));

  return { css, groupColor, fmt, loadJSON, showTip, moveTip, hideTip, onTheme: (f) => themeListeners.push(f) };
})();
