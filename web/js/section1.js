// Section 1: where investment and deprivation sit (teammate pipeline: sections/section1).
(async () => {
  const { css, fmt, loadJSON, showTip, moveTip, hideTip, onTheme } = App;
  let data, boroughsGeo;
  try {
    [data, boroughsGeo] = await Promise.all([loadJSON("data/section1.json"), loadJSON("data/boroughs.geojson")]);
  } catch (e) {
    document.getElementById("s1-lede").textContent = `Could not load Section 1 data (${e.message}).`;
    return;
  }
  const { headlines, areas, trend, boroughs } = data;
  const byCode = Object.fromEntries(boroughs.map((b) => [b.lad24cd, b]));
  const A = Object.fromEntries(areas.map((a) => [a.itl2_name, a]));
  const pct = (v) => (v == null ? "–" : `${Number(v).toFixed(1)}%`);
  const swatch = (c) => `<span class="swatch" style="background:${c}"></span>`;

  // ------------------------------------------------------------ lede + stats
  document.getElementById("s1-lede").textContent =
    `${headlines.primary.text}. Inner East holds the largest share of deprivation (${pct(A["Inner East"].deprivation_share)}) but gets ${pct(A["Inner East"].fdi_share_2024_25)} of projects.`;
  const top = [...boroughs].sort((a, b) => b.dep_pct_london - a.dep_pct_london)[0];
  document.getElementById("s1-stats").innerHTML = [
    [pct(A["Inner West"].fdi_share_2024_25), "of London's FDI projects go to Inner West (2024-25)"],
    [pct(A["Inner West"].deprivation_share), "of London's most deprived neighbourhoods are in Inner West"],
    [`${headlines.secondary.values.per_head_ratio.toFixed(0)}×`, "more FDI projects per head in Inner West than Outer East & NE"],
    [pct(top.dep_pct_london), `of ${top.lad24nm}'s neighbourhoods are in London's most deprived 20%`],
  ]
    .map(([v, l]) => `<div class="stat"><div class="value">${v}</div><div class="label">${l}</div></div>`)
    .join("");

  const SERIES = [
    { key: "fdi_share_2024_25", label: "Share of London FDI projects", color: () => css("--s-1") },
    { key: "deprivation_share", label: "Share of London's most deprived neighbourhoods", color: () => css("--s-2") },
  ];

  // ------------------------------------------------------------ grouped bars
  function renderBars() {
    document.getElementById("s1-bars-legend").innerHTML = SERIES.map(
      (s) => `<span class="item">${swatch(s.color())}${s.label}</span>`
    ).join("");
    const el = document.getElementById("s1-bars");
    const W = 900, H = 340, L = 44, R = 10, T = 24, B = 40;
    const max = 70;
    const y = (v) => T + (1 - v / max) * (H - T - B);
    const band = (W - L - R) / areas.length;
    const bw = Math.min(56, band * 0.3), gap = 2;
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Grouped bar chart of FDI share and deprivation share by sub-area">`;
    for (let t = 0; t <= max; t += 10) {
      svg += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}"/>`;
      svg += `<text class="axis-label" x="${L - 8}" y="${y(t) + 4}" text-anchor="end">${t}%</text>`;
    }
    areas.forEach((a, i) => {
      const cx = L + band * i + band / 2;
      SERIES.forEach((s, j) => {
        const v = a[s.key];
        if (v == null) return;
        const x = j === 0 ? cx - bw - gap / 2 : cx + gap / 2;
        const h = H - B - y(v), r = Math.min(4, h);
        // bar with 4px rounded top, square at baseline
        svg += `<path d="M${x},${H - B} V${y(v) + r} Q${x},${y(v)} ${x + r},${y(v)} H${x + bw - r} Q${x + bw},${y(v)} ${x + bw},${y(v) + r} V${H - B} Z" fill="${s.color()}"/>`;
        svg += `<text x="${x + bw / 2}" y="${y(v) - 6}" text-anchor="middle">${Math.round(v)}%</text>`;
      });
      svg += `<rect class="hit" data-i="${i}" x="${cx - band / 2}" y="${T}" width="${band}" height="${H - T - B}"/>`;
      svg += `<text x="${cx}" y="${H - B + 22}" text-anchor="middle">${a.itl2_name}</text>`;
    });
    svg += `<line class="zero" x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}"/></svg>`;
    el.innerHTML = svg;
    el.querySelectorAll(".hit").forEach((h) => {
      h.addEventListener("mouseenter", (e) => {
        const a = areas[+h.dataset.i];
        showTip(e, a.itl2_name, [
          ["FDI projects share", pct(a.fdi_share_2024_25)],
          ["Most-deprived share", pct(a.deprivation_share)],
          ["FDI projects (2024-25)", fmt.int(a.projects_2024_25)],
          ["New jobs (2024-25)", fmt.int(a.new_jobs_2024_25)],
          ["Projects per 100 neighbourhoods", fmt.dec(a.projects_per_100_lsoas, 1)],
        ]);
      });
      h.addEventListener("mousemove", moveTip);
      h.addEventListener("mouseleave", hideTip);
    });
  }

  // ------------------------------------------------------------ borough choropleth
  const BINS = [10, 20, 30, 40]; // % of neighbourhoods in London's most deprived 20%
  const binColor = (v) => css(`--seq-${1 + BINS.filter((b) => v >= b).length}`);
  const map = L.map("s1-map", { zoomSnap: 0.25, scrollWheelZoom: false, attributionControl: true });
  map.attributionControl.setPrefix("").addAttribution("Contains OS & ONS data © Crown copyright 2026");
  const style = (f) => ({
    fillColor: binColor(byCode[f.properties.code].dep_pct_london),
    fillOpacity: 1,
    color: css("--surface"),
    weight: 1.5,
  });
  const layer = L.geoJSON(boroughsGeo, {
    style,
    onEachFeature: (f, lyr) => {
      const b = byCode[f.properties.code];
      lyr.on({
        mouseover: (e) => {
          lyr.setStyle({ weight: 3, color: css("--ink") });
          lyr.bringToFront();
          showTip(e.originalEvent, b.lad24nm, [
            ["Most-deprived neighbourhoods", `${pct(b.dep_pct_london)} (${b.lsoas_london_worst20} of ${b.lsoa_count})`],
            ["London deprivation rank", `${b.london_overall_rank} of 33`],
            ["Sub-area", b.itl2_name],
            ["Sub-area share of FDI projects", pct(b.area_fdi_share_2024_25)],
          ]);
        },
        mousemove: (e) => moveTip(e.originalEvent),
        mouseout: () => { layer.resetStyle(lyr); hideTip(); },
      });
    },
  }).addTo(map);
  map.fitBounds(layer.getBounds(), { padding: [4, 4] });

  function renderMapLegend() {
    const labels = ["< 10%", "10–20%", "20–30%", "30–40%", "≥ 40%"];
    document.getElementById("s1-map-legend").innerHTML = labels
      .map((l, i) => `<span class="item">${swatch(css(`--seq-${i + 1}`))}${l}</span>`)
      .join("");
  }

  // ------------------------------------------------------------ trend line
  const TSERIES = [
    { key: "inner_west_share", label: "Inner West", color: () => css("--s-1") },
    { key: "inner_east_share", label: "Inner East", color: () => css("--s-2") },
  ];
  function renderTrend() {
    document.getElementById("s1-trend-legend").innerHTML = TSERIES.map(
      (s) => `<span class="item">${swatch(s.color())}${s.label}</span>`
    ).join("");
    const el = document.getElementById("s1-trend");
    const W = 520, H = 300, L = 44, R = 70, T = 16, B = 34;
    const x = (i) => L + (i / (trend.length - 1)) * (W - L - R);
    const y = (v) => T + (1 - v / 80) * (H - T - B);
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Line chart of FDI project share by year">`;
    for (let t = 0; t <= 80; t += 20) {
      svg += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}"/>`;
      svg += `<text class="axis-label" x="${L - 8}" y="${y(t) + 4}" text-anchor="end">${t}%</text>`;
    }
    trend.forEach((r, i) => (svg += `<text class="axis-label" x="${x(i)}" y="${H - 10}" text-anchor="middle">${r.year}</text>`));
    TSERIES.forEach((s) => {
      const pts = trend.map((r, i) => `${x(i)},${y(r[s.key])}`).join(" ");
      svg += `<polyline points="${pts}" fill="none" stroke="${s.color()}" stroke-width="2" stroke-linejoin="round"/>`;
      trend.forEach((r, i) => {
        svg += `<circle class="dot" cx="${x(i)}" cy="${y(r[s.key])}" r="5" fill="${s.color()}"/>`;
        svg += `<circle class="hit" data-k="${s.key}" data-i="${i}" cx="${x(i)}" cy="${y(r[s.key])}" r="14"/>`;
      });
      const last = trend[trend.length - 1][s.key];
      svg += `<text x="${x(trend.length - 1) + 12}" y="${y(last) + 4}">${Math.round(last)}%</text>`;
    });
    svg += "</svg>";
    el.innerHTML = svg;
    el.querySelectorAll(".hit").forEach((h) => {
      h.addEventListener("mouseenter", (e) => {
        const r = trend[+h.dataset.i], s = TSERIES.find((t) => t.key === h.dataset.k);
        showTip(e, `${s.label} · ${r.year}`, [
          ["Share of London FDI projects", pct(r[s.key])],
          ["London total projects", fmt.int(r.london_projects)],
        ]);
      });
      h.addEventListener("mousemove", moveTip);
      h.addEventListener("mouseleave", hideTip);
    });
  }

  renderBars();
  renderMapLegend();
  renderTrend();
  onTheme(() => {
    renderBars();
    renderMapLegend();
    renderTrend();
    layer.setStyle(style);
  });
})();
