// Build in London: interactive 3D app (deck.gl). Data from scripts/export_web.py.
(async () => {
  const $ = (id) => document.getElementById(id);

  // ------------------------------------------------------------------ config
  const CRITERIA = [
    { key: "need", label: "Need", desc: "Income, jobs, skills & health deprivation", w: 25 },
    { key: "land", label: "Land ready", desc: "Brownfield homes per resident", w: 20 },
    { key: "underinv", label: "Under-invested today", desc: "Few FDI projects in its sub-area (Section 1)", w: 20 },
    { key: "room", label: "Room to grow", desc: "Lower housing demand today", w: 15 },
    { key: "work", label: "Workforce", desc: "Share of working-age residents", w: 10 },
    { key: "access", label: "Access to services", desc: "Shorter distances to services", w: 10 },
  ];
  const GROUP_RGB = { A: [57, 135, 229], B: [217, 89, 38], C: [25, 158, 112], D: [201, 133, 0] };
  const GROUP_SHORT = {
    A: "High demand + deprived", B: "High demand + not deprived",
    C: "Low demand + deprived", D: "Low demand + not deprived",
  };
  // Sequential ramps for a dark ground: brighter = more.
  const BLUE = ["#14335e", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#b7d3f6"];
  const ORANGE = ["#4a1d0b", "#7a2e10", "#a8421b", "#d95926", "#ec835a", "#f5b896"];
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const ramp = (stops) => {
    const rgb = stops.map(hex);
    return (t) => {
      t = Math.max(0, Math.min(1, t)) * (rgb.length - 1);
      const i = Math.min(Math.floor(t), rgb.length - 2), f = t - i;
      return rgb[i].map((c, k) => Math.round(c + (rgb[i + 1][k] - c) * f));
    };
  };
  const AQUA = ["#08261d", "#0b3a2c", "#0f5c45", "#16815f", "#4cc39a", "#a6e6cc"];
  const blue = ramp(BLUE), orange = ramp(ORANGE), aqua = ramp(AQUA);
  const bin = (v, cuts) => cuts.filter((c) => v >= c).length;
  // Discrete tiers per view: big lightness steps so blocks read as categories, not a blur.
  const TIERS = {
    score: {
      title: "FDI Opportunity Score tier",
      labels: ["Bottom 25%", "50–75%", "25–50%", "Top 10–25%", "Top 10%"],
      colors: ["#1a2b47", "#1f4f8f", "#2f73c9", "#6aa8ef", "#e3efff"].map(hex),
      heights: [120, 700, 1600, 3200, 6200],
      of: (p) => { const q = (p.rank - 1) / feats.length; return q < 0.1 ? 4 : q < 0.25 ? 3 : q < 0.5 ? 2 : q < 0.75 ? 1 : 0; },
    },
    fdi: {
      title: "Borough share of neighbourhoods in London's most deprived 20%",
      labels: ["< 10%", "10–20%", "20–30%", "30–40%", "40%+"],
      colors: ["#4a1d0b", "#8f3614", "#c84e1f", "#ee8d63", "#fbd3bd"].map(hex),
      of: (p) => bin(bByCode[p.bcode].dep_pct_london, [10, 20, 30, 40]),
    },
    housing: {
      title: "Approved new-home schemes per 1,000 new migrants",
      labels: ["< 5", "5–10", "10–20", "20–30", "30+"],
      colors: ["#0a2e23", "#11634a", "#199e70", "#56c9a0", "#c2f0dd"].map(hex),
      of: (p) => bin(s2B[p.bcode].new_homes_approved_per_1000_arrivals, [5, 10, 20, 30]),
    },
    groups: {
      title: "Housing demand × deprivation",
      labels: ["A: High demand + deprived", "B: High demand + not deprived", "C: Low demand + deprived", "D: Low demand + not deprived"],
      colors: ["A", "B", "C", "D"].map((g) => GROUP_RGB[g]),
      of: (p) => "ABCD".indexOf(p.group),
    },
  };

  // ------------------------------------------------------------------ data
  let msoa, boroughs, meta, s1, s2, s3;
  try {
    [msoa, boroughs, meta, s1, s2, s3] = await Promise.all(
      ["app_msoa.geojson", "app_boroughs.geojson", "app_meta.json", "section1.json", "section2.json", "section3.json"].map((f) =>
        fetch(`data/${f}`).then((r) => { if (!r.ok) throw new Error(f); return r.json(); })
      )
    );
  } catch (e) {
    $("loading").textContent = `Could not load data (${e.message}). Run scripts/export_web.py.`;
    return;
  }
  const feats = msoa.features;
  const P = (f) => f.properties;
  const bByCode = Object.fromEntries(boroughs.features.map((f) => [f.properties.code, f.properties]));
  const s2B = Object.fromEntries(s2.boroughs.map((b) => [b.lad24cd, b]));

  // ------------------------------------------------------------------ state
  const state = {
    mode: "score",
    weights: Object.fromEntries(CRITERIA.map((c) => [c.key, c.w])),
    lbTab: "boroughs",
    selected: null, // msoa id or borough code
    focus: null, // legend tier index to isolate
    hover: null,
  };

  function computeScores() {
    const tot = CRITERIA.reduce((s, c) => s + state.weights[c.key], 0) || 1;
    for (const f of feats) {
      const p = P(f);
      p.score = (100 * CRITERIA.reduce((s, c) => s + state.weights[c.key] * p[`p_${c.key}`], 0)) / tot;
    }
    const sorted = [...feats].sort((a, b) => P(b).score - P(a).score);
    sorted.forEach((f, i) => (P(f).rank = i + 1));
    // borough = population-weighted mean of its neighbourhoods
    const agg = {};
    for (const f of feats) {
      const p = P(f), a = (agg[p.bcode] ??= { s: 0, pop: 0, n: 0 });
      a.s += p.score * p.pop; a.pop += p.pop; a.n += 1;
    }
    state.boroughScores = Object.entries(agg)
      .map(([code, a]) => ({ code, name: bByCode[code].name, score: a.s / a.pop, n: a.n }))
      .sort((a, b) => b.score - a.score);
    state.boroughScores.forEach((b, i) => (b.rank = i + 1));
    state.bRank = Object.fromEntries(state.boroughScores.map((b) => [b.code, b]));
    const sc = feats.map((f) => P(f).score);
    state.smin = Math.min(...sc); state.smax = Math.max(...sc);
  }

  // ------------------------------------------------------------------ deck.gl
  const INITIAL = { longitude: -0.115, latitude: 51.455, zoom: 9.35, pitch: 52, bearing: -12, maxPitch: 75 };
  const lighting = new deck.LightingEffect({
    ambient: new deck.AmbientLight({ color: [255, 255, 255], intensity: 0.75 }),
    sun: new deck.DirectionalLight({ color: [255, 245, 230], intensity: 0.9, direction: [-3, -6, -8] }),
    rim: new deck.DirectionalLight({ color: [120, 160, 255], intensity: 0.35, direction: [4, 6, -2] }),
  });

  const elev = (p) => {
    if (state.mode === "fdi") return 60 + p.fdi_per100 * 70;
    if (state.mode === "housing") return 60 + Math.pow(s2B[p.bcode].arrived_from_abroad_per_1000, 1.4) * 22;
    if (state.mode === "groups") return 40 + Math.min(p.bf_per1k, 400) * 9;
    return TIERS.score.heights[TIERS.score.of(p)];
  };
  const fill = (p) => {
    const T = TIERS[state.mode], k = T.of(p);
    const dimSel = state.selected && !["fdi", "housing"].includes(state.mode) && !isSelected(p);
    const dimFocus = state.focus !== null && k !== state.focus;
    return [...T.colors[k], dimFocus ? 28 : dimSel ? 70 : 250];
  };
  const isSelected = (p) => state.selected === p.id || state.selected === p.bcode;

  let version = 0; // bump to retrigger accessors
  function layers() {
    const top5 = state.boroughScores.slice(0, 5).map((b) => b.code);
    const labels =
      state.mode === "score"
        ? boroughs.features.filter((f) => top5.includes(f.properties.code))
        : state.mode === "fdi"
        ? boroughs.features.filter((f) => ["E09000033", "E09000030", "E09000002", "E09000025", "E09000008"].includes(f.properties.code))
        : state.mode === "housing"
        ? boroughs.features.filter((f) => ["E09000001", "E09000030", "E09000025", "E09000004", "E09000016"].includes(f.properties.code))
        : [];
    return [
      new deck.GeoJsonLayer({
        id: "ground",
        data: boroughs,
        filled: true, stroked: false, extruded: false,
        getFillColor: [22, 30, 46, 255],
        pickable: false,
      }),
      new deck.GeoJsonLayer({
        id: "msoa",
        data: msoa,
        extruded: true, wireframe: true, pickable: true, autoHighlight: true,
        getLineColor: [7, 11, 20, 210],
        elevationScale: state.selected ? 0.3 : 1, // flatten the city around a selection so context stays visible
        highlightColor: [255, 255, 255, 90],
        getElevation: (f) => elev(P(f)),
        getFillColor: (f) => fill(P(f)),
        material: { ambient: 0.55, diffuse: 0.55, shininess: 24, specularColor: [40, 50, 70] },
        updateTriggers: { getElevation: [state.mode, version], getFillColor: [state.mode, version, state.selected, state.focus] },
        transitions: {
          getElevation: { duration: 900, easing: (t) => 1 - Math.pow(1 - t, 3) },
          getFillColor: { duration: 600 },
        },
        onHover: onHover,
        onClick: ({ object }) => object && select(P(object).id, true),
      }),
      new deck.GeoJsonLayer({
        id: "borough-lines",
        data: boroughs,
        filled: false, stroked: true, lineWidthMinPixels: 1.2,
        getLineColor: [230, 236, 248, 110],
        pickable: false,
      }),
      new deck.TextLayer({
        id: "labels",
        data: labels,
        getPosition: (f) => [f.properties.lon, f.properties.lat, state.mode === "fdi" ? 4200 : state.mode === "housing" ? 5600 : 3200],
        getText: (f) =>
          state.mode === "score" ? `${state.bRank[f.properties.code].rank}. ${f.properties.name}` : f.properties.name,
        getSize: 13, getColor: [240, 239, 236, 255],
        fontFamily: "Inter, system-ui, sans-serif", fontWeight: 600,
        background: true, getBackgroundColor: [18, 22, 32, 225], backgroundPadding: [8, 4],
        getBorderColor: [255, 255, 255, 50], getBorderWidth: 1,
        billboard: true, sizeUnits: "pixels",
        parameters: { depthCompare: "always" },
        updateTriggers: { getText: [state.mode, version], getPosition: [state.mode] },
      }),
    ];
  }

  const deckgl = new deck.DeckGL({
    container: "map",
    initialViewState: INITIAL,
    controller: { dragRotate: true, touchRotate: true, inertia: true },
    effects: [lighting],
    layers: [],
    getCursor: ({ isHovering, isDragging }) => (isDragging ? "grabbing" : isHovering ? "pointer" : "grab"),
  });
  let viewState = INITIAL;
  deckgl.setProps({ onViewStateChange: ({ viewState: v }) => { viewState = v; } });
  const render = () => deckgl.setProps({ layers: layers() });
  const flyTo = (lon, lat, zoom = 11.6, extra = {}) =>
    deckgl.setProps({
      initialViewState: {
        ...viewState, longitude: lon, latitude: lat, zoom, pitch: 48, ...extra,
        transitionDuration: 1600, transitionInterpolator: new deck.FlyToInterpolator(),
      },
    });

  // ------------------------------------------------------------------ tooltip
  const tip = $("tip");
  function onHover({ object, x, y }) {
    if (!object) { tip.hidden = true; return; }
    const p = P(object), b = bByCode[p.bcode];
    const rows =
      state.mode === "fdi"
        ? [["Sub-area", p.area], ["FDI projects / 100 neighbourhoods", p.fdi_per100.toFixed(1)],
           ["Sub-area share of London FDI", `${p.fdi_share.toFixed(1)}%`],
           ["Borough in most-deprived 20%", `${b.dep_pct_london.toFixed(1)}%`]]
        : state.mode === "housing"
        ? (() => { const h = s2B[p.bcode]; return [
            ["Migrants from abroad / 1,000 residents", h.arrived_from_abroad_per_1000.toFixed(1)],
            ["New-home schemes approved / 1,000 new migrants", h.new_homes_approved_per_1000_arrivals.toFixed(1)],
            ["New-home approval rate", `${h.new_home_approval_rate.toFixed(0)}%`],
            ["Sub-area share of London FDI", `${p.fdi_share.toFixed(1)}%`]]; })()
        : state.mode === "groups"
        ? [["Group", `${p.group}: ${GROUP_SHORT[p.group]}`], ["Brownfield homes / 1,000", Math.round(p.bf_per1k)],
           ["Brownfield sites", p.bf_sites], ["Deprivation index", p.dep.toFixed(2)]]
        : [["Opportunity score", p.score.toFixed(1)], ["Rank", `${p.rank} of ${feats.length}`],
           ["Group", `${p.group}: ${GROUP_SHORT[p.group]}`], ["Brownfield homes", Math.round(p.bf_homes).toLocaleString("en-GB")]];
    rows.unshift([TIERS[state.mode].title.split(" (")[0].replace("Borough share of neighbourhoods in London's most deprived 20%", "Deprivation band"), TIERS[state.mode].labels[TIERS[state.mode].of(p)]]);
    tip.innerHTML = `<b class="t">${p.name} · ${p.borough}</b>` +
      rows.map(([k, v]) => `<div class="r"><span>${k}</span><span>${v}</span></div>`).join("");
    tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = `${x + 16 + w > innerWidth ? x - w - 16 : x + 16}px`;
    tip.style.top = `${y + 16 + h > innerHeight ? y - h - 16 : y + 16}px`;
  }

  // ------------------------------------------------------------------ sliders
  function renderSliders() {
    $("sliders").innerHTML = CRITERIA.map(
      (c) => `<div class="slider">
        <div class="slider-top"><span class="slider-label">${c.label}</span><span class="slider-val" id="v-${c.key}"></span></div>
        <div class="slider-desc">${c.desc}</div>
        <input type="range" min="0" max="50" step="1" value="${state.weights[c.key]}" data-k="${c.key}" aria-label="${c.label} weight">
      </div>`
    ).join("");
    $("sliders").querySelectorAll("input").forEach((inp) => {
      inp.addEventListener("input", () => {
        state.weights[inp.dataset.k] = +inp.value;
        if (state.mode !== "score") setMode("score", false);
        update();
      });
    });
    syncSliderLabels();
  }
  function syncSliderLabels() {
    const tot = CRITERIA.reduce((s, c) => s + state.weights[c.key], 0) || 1;
    CRITERIA.forEach((c) => {
      $(`v-${c.key}`).textContent = `${Math.round((100 * state.weights[c.key]) / tot)}%`;
      const inp = document.querySelector(`input[data-k="${c.key}"]`);
      inp.value = state.weights[c.key];
      inp.style.setProperty("--fill", `${(state.weights[c.key] / 50) * 100}%`);
    });
  }
  $("reset").addEventListener("click", () => {
    CRITERIA.forEach((c) => (state.weights[c.key] = c.w));
    update();
  });

  // ------------------------------------------------------------------ legend
  function renderLegend() {
    const T = TIERS[state.mode];
    const counts = T.labels.map(() => 0);
    feats.forEach((f) => counts[T.of(P(f))]++);
    const order = state.mode === "groups" ? [0, 1, 2, 3] : [...T.labels.keys()].reverse(); // highest tier first
    const note =
      state.mode === "score" ? "Height steps up with each tier."
      : state.mode === "fdi" ? "Height: FDI projects per 100 neighbourhoods (sub-area, 2024-25)."
      : state.mode === "housing" ? "Height: migrants from abroad per 1,000 residents (Census 2021)."
      : `Height: brownfield homes per resident. Demand: ${meta.demand_label}.`;
    $("legend").innerHTML =
      `<div class="legend-title">${T.title}</div>` +
      order.map((i) => `<button type="button" class="tier${state.focus === i ? " on" : ""}${state.focus !== null && state.focus !== i ? " off" : ""}" data-i="${i}">
        <span class="sw" style="background:rgb(${T.colors[i]})"></span><span class="tl">${T.labels[i]}</span><span class="tc">${counts[i]}</span></button>`).join("") +
      `<div class="legend-note">${note} Click a band to isolate it.</div>`;
    $("legend").querySelectorAll(".tier").forEach((b) =>
      b.addEventListener("click", () => {
        const i = +b.dataset.i;
        state.focus = state.focus === i ? null : i;
        renderLegend(); render();
      })
    );
    $("left").classList.toggle("dim", state.mode !== "score");
    $("left-title").textContent = state.mode === "score" ? "Your priorities" : "Map key";
    $("reset").hidden = state.mode !== "score";
  }

  // ------------------------------------------------------------------ right panel
  function renderRight() {
    const el = $("right-content");
    if (state.mode === "fdi") {
      const max = 70;
      el.innerHTML = `<span class="pill">Section 1</span><h3>Where overseas investment goes</h3>
        <p class="sub">${meta.s1_headline}.</p>
        <div class="stat"><div class="stat-v">27×</div><div class="stat-l">more FDI projects per head in Inner West than Outer East &amp; NE</div></div>
        <div class="cat"><span class="sw" style="background:var(--g-A)"></span>Share of London FDI projects</div>
        <div class="cat"><span class="sw" style="background:var(--g-B)"></span>Share of London's most deprived neighbourhoods</div>
        ${s1.areas.map((a) => `<div class="mini-row"><div class="mini-name"><span>${a.itl2_name}</span></div>
          <div class="mini-bar"><span class="b" style="width:${(a.fdi_share_2024_25 / max) * 85}%;background:var(--g-A)"></span><span class="v">${a.fdi_share_2024_25}%</span></div>
          <div class="mini-bar"><span class="b" style="width:${(a.deprivation_share / max) * 85}%;background:var(--g-B)"></span><span class="v">${a.deprivation_share}%</span></div></div>`).join("")}
        <p class="sub" style="margin-top:10px">Source: DBT Inward Investment Results 2025-26; IoD 2025. FDI published for 5 sub-areas only.</p>`;
      return;
    }
    if (state.mode === "housing") {
      const max = 70, H = s2.headlines, cw = s2.canary_wharf;
      const SER = [["fdi_share_2024_25", "Share of London FDI projects", "var(--g-A)"],
        ["share_of_london_arrivals_from_abroad", "Share of migrants from abroad", "var(--g-B)"],
        ["share_of_london_new_home_approvals", "Share of approved new-home schemes", "var(--g-C)"]];
      el.innerHTML = `<span class="pill">Section 2</span><h3>Is housing keeping up with FDI and newcomers?</h3>
        <p class="sub">${H.primary.text}.</p>
        <div class="stat"><div class="stat-v">${Math.round(H.secondary.values.outer_schemes_per_1000_arrivals / H.secondary.values.inner_schemes_per_1000_arrivals)}×</div>
          <div class="stat-l">more new-home schemes approved per new migrant in outer London (${H.secondary.values.outer_schemes_per_1000_arrivals}) than inner (${H.secondary.values.inner_schemes_per_1000_arrivals})</div></div>
        <div class="stat"><div class="stat-v">${cw.new_home_approved} of ${cw.new_home_applications}</div>
          <div class="stat-l">new-home applications approved in the Canary Wharf cluster, 2021-25 (small numbers: indicative)</div></div>
        ${SER.map(([, l, c]) => `<div class="cat"><span class="sw" style="background:${c}"></span>${l}</div>`).join("")}
        ${s2.areas.map((a) => `<div class="mini-row"><div class="mini-name"><span>${a.itl2_name}</span></div>
          ${SER.map(([k, , c]) => `<div class="mini-bar"><span class="b" style="width:${(a[k] / max) * 85}%;background:${c}"></span><span class="v">${a[k]}%</span></div>`).join("")}</div>`).join("")}
        <p class="sub" style="margin-top:10px">Counts planning schemes, not homes. Migration: Census 2021 (during COVID-19). Association, not causation.</p>`;
      return;
    }
    if (state.mode === "groups") {
      const S = Object.fromEntries(s3.summary.map((r) => [r.group, r]));
      el.innerHTML = `<span class="pill">Section 3</span><h3>What deprived areas are missing</h3>
        <p class="sub">They have land. Deprived, lower-demand neighbourhoods (C) hold
        ${(S.C.bf_homes_per_1k / S.B.bf_homes_per_1k).toFixed(1)}× the brownfield capacity per resident of high-demand, better-off areas (B).</p>
        ${["A", "B", "C", "D"].map((g) => `<div class="stat" style="border-left:4px solid rgb(${GROUP_RGB[g]})">
          <div class="stat-v">${Math.round(S[g].bf_homes_per_1k)}<span style="font-size:13px;color:var(--muted)"> homes / 1,000</span></div>
          <div class="stat-l">${g}: ${GROUP_SHORT[g]} · ${S[g].n_msoas} neighbourhoods</div></div>`).join("")}
`;
      return;
    }
    const list =
      state.lbTab === "boroughs"
        ? state.boroughScores.slice(0, 12).map((b) => ({ id: b.code, name: b.name, meta: `${b.n} neighbourhoods`, score: b.score }))
        : [...feats].sort((a, b) => P(a).rank - P(b).rank).slice(0, 12)
            .map((f) => ({ id: P(f).id, name: P(f).name, meta: P(f).borough, score: P(f).score }));
    const top = list[0].score;
    el.innerHTML = `<span class="pill">Leaderboard</span>
      <p class="sub" style="margin-top:8px">Ranked by your priorities. Click to fly there.</p>
      <div class="tabs" role="tablist">
        <button role="tab" data-t="boroughs" aria-selected="${state.lbTab === "boroughs"}">Boroughs</button>
        <button role="tab" data-t="msoas" aria-selected="${state.lbTab === "msoas"}">Neighbourhoods</button></div>
      <ol class="lb">${list.map((r, i) => `<li data-id="${r.id}" class="${state.selected === r.id ? "sel" : ""}">
        <span class="lb-rank">${i + 1}</span>
        <div><div class="lb-name">${r.name}</div><div class="lb-meta">${r.meta}</div>
          <div class="lb-bar"><span style="width:${(r.score / top) * 100}%"></span></div></div>
        <span class="lb-score">${r.score.toFixed(1)}</span></li>`).join("")}</ol>`;
    el.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => { state.lbTab = b.dataset.t; renderRight(); }));
    el.querySelectorAll(".lb li").forEach((li) => li.addEventListener("click", () => select(li.dataset.id, true)));
  }

  // ------------------------------------------------------------------ selection & detail
  function centroidOf(id) {
    if (bByCode[id]) return [bByCode[id].lon, bByCode[id].lat, 11.2];
    const f = feats.find((x) => P(x).id === id);
    let sx = 0, sy = 0, n = 0;
    const walk = (c) => (typeof c[0] === "number" ? (sx += c[0], sy += c[1], n++) : c.forEach(walk));
    walk(f.geometry.coordinates);
    return [sx / n, sy / n, 11.6];
  }
  function select(id, fly) {
    state.selected = state.selected === id && !fly ? null : id;
    if (fly && id) {
      // offset east so the target sits left of centre, clear of the detail card
      const [lon, lat, z] = centroidOf(id);
      flyTo(lon + 0.09 * Math.pow(2, 11.2 - z), lat, z);
    }
    renderDetail(); renderRight(); render();
  }
  function renderDetail() {
    const d = $("detail");
    if (!state.selected) { d.hidden = true; return; }
    const isB = !!bByCode[state.selected];
    let title, where, score, rank, pcts, facts;
    if (isB) {
      const b = bByCode[state.selected], r = state.bRank[state.selected];
      const fs = feats.filter((f) => P(f).bcode === state.selected);
      const wavg = (k) => fs.reduce((s, f) => s + P(f)[k] * P(f).pop, 0) / fs.reduce((s, f) => s + P(f).pop, 0);
      title = b.name; where = `${b.itl2_name} · ${fs.length} neighbourhoods`;
      score = r.score; rank = `${r.rank} of 33 boroughs`;
      pcts = Object.fromEntries(CRITERIA.map((c) => [c.key, wavg(`p_${c.key}`)]));
      const best = [...fs].sort((a, b2) => P(b2).score - P(a).score)[0];
      facts = [["Most-deprived 20%", `${b.dep_pct_london.toFixed(1)}% of areas`], ["Deprivation rank", `${b.london_overall_rank} of 33`],
        ["Sub-area FDI share", `${b.area_fdi_share_2024_25}%`], ["Top neighbourhood", P(best).name]];
    } else {
      const p = P(feats.find((f) => P(f).id === state.selected));
      title = p.name; where = `${p.borough} · ${p.area}`;
      score = p.score; rank = `${p.rank} of ${feats.length} neighbourhoods`;
      pcts = Object.fromEntries(CRITERIA.map((c) => [c.key, p[`p_${c.key}`]]));
      facts = [["Group", `<span class="badge"><span class="sw" style="background:rgb(${GROUP_RGB[p.group]})"></span>${p.group}</span>`],
        ["Population", p.pop.toLocaleString("en-GB")], ["Brownfield homes", Math.round(p.bf_homes).toLocaleString("en-GB")],
        ["Sub-area FDI share", `${p.fdi_share}%`]];
    }
    d.innerHTML = `<button class="ghost close" id="close" type="button" aria-label="Close">✕</button>
      <h3>${title}</h3><div class="where">${where}</div>
      <div class="score-big"><b>${score.toFixed(1)}</b><span class="where">Opportunity score · ${rank}</span></div>
      ${CRITERIA.map((c) => `<div class="crit"><span>${c.label}</span><div class="track"><span style="width:${pcts[c.key] * 100}%"></span></div>
        <span class="n">${Math.round(pcts[c.key] * 100)}</span></div>`).join("")}
      <div class="where" style="margin-top:4px">Bars: London percentile (100 = best on that factor)</div>
      <div class="facts">${facts.map(([k, v]) => `<div><span>${k}</span>${v}</div>`).join("")}</div>`;
    d.hidden = false;
    $("close").addEventListener("click", () => { state.selected = null; renderDetail(); renderRight(); render(); });
  }

  // ------------------------------------------------------------------ search
  $("places").innerHTML =
    boroughs.features.map((f) => `<option value="${f.properties.name}">`).join("") +
    feats.map((f) => `<option value="${P(f).name}">`).join("");
  $("search").addEventListener("change", (e) => {
    const q = e.target.value.trim().toLowerCase();
    const b = boroughs.features.find((f) => f.properties.name.toLowerCase() === q);
    const m = feats.find((f) => P(f).name.toLowerCase() === q);
    if (b) select(b.properties.code, true);
    else if (m) select(P(m).id, true);
  });

  // ------------------------------------------------------------------ modes
  function setMode(mode, rerender = true) {
    state.mode = mode;
    state.focus = null;
    document.querySelectorAll(".seg button").forEach((b) => b.setAttribute("aria-selected", b.dataset.mode === mode));
    if (rerender) { renderLegend(); renderRight(); render(); }
  }
  document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));

  function update() {
    computeScores(); version++;
    syncSliderLabels(); renderLegend(); renderRight(); renderDetail(); render();
  }

  // ------------------------------------------------------------------ story tour
  const S3 = Object.fromEntries(s3.summary.map((r) => [r.group, r]));
  const STEPS = [
    { mode: "fdi", title: "1 · Investment piles up in Inner West London",
      text: `${meta.s1_headline}. Tower height = FDI projects per 100 neighbourhoods; colour = deprivation.`,
      view: { longitude: -0.12, latitude: 51.48, zoom: 9.55, pitch: 55, bearing: -20 } },
    { mode: "housing", title: "2 · Migrants settle where FDI is, but homes get approved further out",
      text: `${s2.headlines.primary.text}. Outer London approves about ${Math.round(s2.headlines.secondary.values.outer_schemes_per_1000_arrivals / s2.headlines.secondary.values.inner_schemes_per_1000_arrivals)}× more new-home schemes per new migrant. Canary Wharf cluster: ${s2.canary_wharf.new_home_approved} of ${s2.canary_wharf.new_home_applications} new-home applications approved.`,
      view: { longitude: -0.1, latitude: 51.49, zoom: 9.7, pitch: 55, bearing: 15 } },
    { mode: "groups", title: "3 · Deprived areas have the land",
      text: `Group C neighbourhoods (green) hold ${(S3.C.bf_homes_per_1k / S3.B.bf_homes_per_1k).toFixed(1)}× the brownfield capacity per resident of group B. What they lack is income, jobs, skills and health.`,
      view: { longitude: -0.1, latitude: 51.44, zoom: 9.9, pitch: 55, bearing: -5 } },
    { mode: "score", title: "4 · Where the next investment should go",
      text: "Combine need, land, under-investment and access into one score. Drag the sliders to test your own priorities; the leaderboard re-ranks live.",
      view: INITIAL },
  ];
  let step = -1;
  $("tour-steps").innerHTML = STEPS.map((_, i) => `<button type="button" data-i="${i}" aria-label="Step ${i + 1}"></button>`).join("");
  function goStep(i) {
    step = Math.max(0, Math.min(STEPS.length - 1, i));
    const s = STEPS[step];
    state.selected = null; renderDetail();
    setMode(s.mode);
    deckgl.setProps({ initialViewState: { ...s.view, transitionDuration: 2000, transitionInterpolator: new deck.FlyToInterpolator() } });
    $("tour-title").textContent = s.title;
    $("tour-text").textContent = s.text;
    document.querySelectorAll(".tour-steps button").forEach((b, k) => b.classList.toggle("on", k <= step));
    $("tour-prev").disabled = step === 0;
    $("tour-next").disabled = step === STEPS.length - 1;
  }
  $("tour-next").addEventListener("click", () => goStep(step + 1));
  $("tour-prev").addEventListener("click", () => goStep(step - 1));
  $("tour-steps").addEventListener("click", (e) => e.target.dataset.i && goStep(+e.target.dataset.i));
  $("tour-title").textContent = "Take the 60-second tour";
  $("tour-text").textContent = "Four steps from where FDI goes today to where it could go next. Drag to rotate; scroll to zoom.";
  $("tour-prev").disabled = true;

  // ------------------------------------------------------------------ go
  computeScores();
  renderSliders();
  renderLegend();
  renderRight();
  render();
  addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT") return;
    if (e.key === "ArrowRight") goStep(step + 1);
    if (e.key === "ArrowLeft") goStep(step - 1);
    if (e.key === "Escape") { state.selected = null; renderDetail(); renderRight(); render(); }
  });
  requestAnimationFrame(() => $("loading").classList.add("done"));
})();
