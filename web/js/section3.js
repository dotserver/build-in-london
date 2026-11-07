// Section 3: what deprived areas are missing (four-group classification).
(async () => {
  const { groupColor, fmt, loadJSON, showTip, moveTip, hideTip, onTheme } = App;
  const GROUPS = ["A", "B", "C", "D"];
  const SHORT = {
    A: "High demand + deprived",
    B: "High demand + not deprived",
    C: "Low demand + deprived",
    D: "Low demand + not deprived",
  };

  let data, msoa, boroughs;
  try {
    [data, msoa, boroughs] = await Promise.all([
      loadJSON("data/section3.json"),
      loadJSON("data/section3_msoa.geojson"),
      loadJSON("data/boroughs.geojson"),
    ]);
  } catch (e) {
    document.getElementById("s3-lede").textContent = `Could not load Section 3 data (${e.message}). Run scripts/export_web.py.`;
    return;
  }

  const { meta, summary, profile, candidates } = data;
  const S = Object.fromEntries(summary.map((r) => [r.group, r]));

  // ------------------------------------------------------------ lede + stats
  const ratio = S.C.bf_homes_per_1k / S.B.bf_homes_per_1k;
  document.getElementById("s3-lede").textContent =
    `Deprived neighbourhoods with lower housing demand (group C) hold ${ratio.toFixed(1)}× more brownfield housing capacity per resident than the high-demand, better-off areas (group B). They have land; what they lack is income, jobs, skills and health.`;

  const stats = [
    [fmt.int(S.C.n_msoas), `group C neighbourhoods, home to ${(S.C.population / 1e6).toFixed(1)}m Londoners`],
    [fmt.int(S.C.bf_homes_per_1k), "brownfield homes per 1,000 residents in group C"],
    [fmt.int(S.B.bf_homes_per_1k), "…versus group B (high demand, not deprived)"],
    [fmt.int(S.C.bf_max_dwellings), "potential homes on group C brownfield sites (lower bound)"],
  ];
  document.getElementById("s3-stats").innerHTML = stats
    .map(([v, l]) => `<div class="stat"><div class="value">${v}</div><div class="label">${l}</div></div>`)
    .join("");

  document.getElementById("s3-map-note").textContent =
    `${meta.n_msoas.toLocaleString("en-GB")} MSOAs, ${meta.split}. Demand axis: ${meta.demand_label}.`;

  // ------------------------------------------------------------ legend / filter
  const active = new Set(GROUPS);
  const legend = document.getElementById("s3-legend");
  function renderLegend() {
    legend.innerHTML = GROUPS.map(
      (g) =>
        `<button type="button" data-g="${g}" aria-pressed="${active.has(g)}">` +
        `<span class="swatch" style="background:${groupColor(g)}"></span>${g}: ${SHORT[g]} (${S[g].n_msoas})</button>`
    ).join("");
  }
  legend.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    const g = b.dataset.g;
    active.has(g) ? active.delete(g) : active.add(g);
    if (active.size === 0) GROUPS.forEach((x) => active.add(x)); // never show an empty map
    renderLegend();
    restyle();
  });

  // ------------------------------------------------------------ map
  const map = L.map("s3-map", { zoomSnap: 0.25, attributionControl: true, scrollWheelZoom: false });
  map.attributionControl.setPrefix("").addAttribution("Contains OS & ONS data © Crown copyright 2026");

  const style = (f) => {
    const on = active.has(f.properties.group);
    return {
      fillColor: groupColor(f.properties.group),
      fillOpacity: on ? 0.85 : 0.08,
      color: App.css("--surface"),
      weight: 0.5,
    };
  };
  const layer = L.geoJSON(msoa, {
    style,
    onEachFeature: (f, lyr) => {
      const p = f.properties;
      lyr.on({
        mouseover: (e) => {
          lyr.setStyle({ weight: 2, color: App.css("--ink") });
          lyr.bringToFront();
          showTip(e.originalEvent, `${p.msoa21nm} · ${p.lad24nm}`, [
            ["Group", `${p.group}: ${SHORT[p.group]}`],
            ["Deprivation index", fmt.dec(p.deprivation_index)],
            ["Demand index", fmt.dec(p.demand_index)],
            ["Population", fmt.int(p.total_population_mid_2022)],
            ["Brownfield sites", fmt.int(p.bf_sites)],
            ["Brownfield homes (max)", fmt.int(p.bf_max_dwellings)],
          ]);
        },
        mousemove: (e) => moveTip(e.originalEvent),
        mouseout: () => {
          layer.resetStyle(lyr);
          bLayer.bringToFront();
          hideTip();
        },
      });
    },
  }).addTo(map);
  const bLayer = L.geoJSON(boroughs, {
    style: () => ({ fill: false, color: App.css("--ink"), weight: 1, opacity: 0.6 }),
    interactive: false,
  }).addTo(map);
  map.fitBounds(layer.getBounds(), { padding: [8, 8] });

  function restyle() {
    layer.setStyle(style);
    bLayer.setStyle({ color: App.css("--ink") });
    renderProfile();
  }

  // ------------------------------------------------------------ profile dot plot
  function renderProfile() {
    const el = document.getElementById("s3-profile");
    const W = 900, rowH = 38, top = 28, left = 300, right = 30;
    const H = top + profile.length * rowH + 30;
    const all = profile.flatMap((r) => GROUPS.map((g) => r.z[g]).filter((v) => v != null));
    const ext = Math.max(1, Math.ceil(Math.max(...all.map(Math.abs)) * 2) / 2);
    const x = (v) => left + ((v + ext) / (2 * ext)) * (W - left - right);
    const ticks = [];
    for (let t = -ext; t <= ext + 1e-9; t += 0.5) ticks.push(+t.toFixed(1));

    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Dot plot of group averages by indicator">`;
    ticks.forEach((t) => {
      svg += `<line class="${t === 0 ? "zero" : "grid"}" x1="${x(t)}" x2="${x(t)}" y1="${top - 8}" y2="${H - 26}"/>`;
      svg += `<text class="axis-label" x="${x(t)}" y="${H - 8}" text-anchor="middle">${t > 0 ? "+" : ""}${t}</text>`;
    });
    svg += `<text class="axis-label" x="${x(0)}" y="${top - 14}" text-anchor="middle">London average</text>`;

    profile.forEach((r, i) => {
      const y = top + i * rowH + rowH / 2;
      const vals = GROUPS.map((g) => r.z[g]).filter((v) => v != null);
      svg += `<text x="${left - 14}" y="${y + 4}" text-anchor="end">${r.label}</text>`;
      svg += `<line class="row-line" x1="${x(Math.min(...vals))}" x2="${x(Math.max(...vals))}" y1="${y}" y2="${y}"/>`;
      GROUPS.forEach((g) => {
        if (r.z[g] == null) return;
        const on = active.has(g);
        svg += `<circle class="dot" cx="${x(r.z[g])}" cy="${y}" r="7" fill="${groupColor(g)}" opacity="${on ? 1 : 0.15}"/>`;
        svg += `<circle class="hit" data-row="${i}" data-g="${g}" cx="${x(r.z[g])}" cy="${y}" r="13"/>`;
      });
    });
    svg += "</svg>";
    el.innerHTML = svg;

    el.querySelectorAll(".hit").forEach((c) => {
      c.addEventListener("mouseenter", (e) => {
        const r = profile[+c.dataset.row], g = c.dataset.g;
        const raw = r.key.startsWith("pct_") ? fmt.pct(r.raw[g]) : fmt.dec(r.raw[g], r.key.startsWith("bf_") ? 0 : 3);
        showTip(e, `${g}: ${SHORT[g]}`, [
          [r.label, ""],
          ["vs London average", `${r.z[g] > 0 ? "+" : ""}${fmt.dec(r.z[g])} SD`],
          ["Group average (raw)", raw],
        ]);
      });
      c.addEventListener("mousemove", moveTip);
      c.addEventListener("mouseleave", hideTip);
    });
  }

  // ------------------------------------------------------------ candidates table
  function renderTable() {
    const head = `<thead><tr><th>#</th><th>Neighbourhood (MSOA)</th><th>Borough</th>
      <th class="num">Deprivation</th><th class="num">Demand</th>
      <th class="num">Brownfield sites</th><th class="num">Max homes</th><th class="num">Sites w/o estimate</th></tr></thead>`;
    const body = candidates
      .map(
        (c, i) => `<tr><td>${i + 1}</td><td>${c.msoa21nm}</td><td>${c.lad24nm}</td>
        <td class="num">${fmt.dec(c.deprivation_index)}</td><td class="num">${fmt.dec(c.demand_index)}</td>
        <td class="num">${fmt.int(c.bf_sites)}</td><td class="num">${fmt.int(c.bf_max_dwellings)}</td>
        <td class="num">${fmt.int(c.bf_sites_missing_dwellings)}</td></tr>`
      )
      .join("");
    document.getElementById("s3-candidates").innerHTML = head + `<tbody>${body}</tbody>`;
  }

  // ------------------------------------------------------------ method
  document.getElementById("s3-method").innerHTML = [
    "Unit: 2021 MSOAs in London (≈8,000 residents each). Deprivation = population-weighted IoD 2025 income, employment, education/skills and health scores, z-scored and combined with official IMD weights. Barriers-to-housing is excluded so it cannot double-count with the demand axis.",
    "Unmet housing demand: IoD 2025 wider-barriers sub-domain (overcrowding, homelessness and housing affordability), population-weighted to MSOAs. It is correlated with deprivation (r ≈ 0.7), so groups B and C are smaller than A and D.",
    "Groups: median split on each axis within London.",
    "Brownfield: active sites on local brownfield land registers (planning.data.gov.uk), located to LSOAs. Sites > 100 ha treated as entry errors; ~32% of sites lack a dwelling estimate (e.g. all of Tower Hamlets and Enfield), so homes are lower bounds.",
    "Associations only: these groups describe where conditions differ, not what causes them.",
  ]
    .map((t) => `<li>${t}</li>`)
    .join("");

  renderLegend();
  renderProfile();
  renderTable();
  onTheme(() => { renderLegend(); restyle(); });
})();
