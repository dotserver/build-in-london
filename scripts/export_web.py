"""Export analysis outputs to small JSON/GeoJSON files for the static web app (web/data/).

Run:  uv run python scripts/export_web.py
Each section gets its own export function; add teammates' sections the same way.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

from house_london_hackathon.classify import GROUP_LABELS, classify, msoa_geometries
from house_london_hackathon.data import load_borough_boundaries

ROOT = Path(__file__).resolve().parents[1]
WEB_DATA = ROOT / "web" / "data"
SIMPLIFY_M = 25  # metres; keeps the MSOA GeoJSON small without visible loss at city scale


def _clean(v):
    if isinstance(v, float):
        return None if math.isnan(v) else round(v, 4)
    return v


def _nan_to_none(o):
    """json.dumps writes NaN as a bare token browsers reject; suppressed values must be null."""
    if isinstance(o, dict):
        return {k: _nan_to_none(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_nan_to_none(v) for v in o]
    if isinstance(o, float) and math.isnan(o):
        return None
    return o


def _write(name: str, obj) -> None:
    path = WEB_DATA / name
    path.write_text(json.dumps(_nan_to_none(obj), separators=(",", ":"), default=_clean, allow_nan=False))
    print(f"  {path.relative_to(ROOT)}  ({path.stat().st_size / 1024:.0f} KB)")


def _geojson(gdf) -> dict:
    gdf = gdf.copy()
    gdf["geometry"] = gdf.to_crs(27700).simplify(SIMPLIFY_M).to_crs(4326).set_precision(1e-5)
    return json.loads(gdf.to_json(drop_id=True))


# --------------------------------------------------------------------------- shared
def export_boroughs() -> None:
    _write("boroughs.geojson", _geojson(load_borough_boundaries()))


# --------------------------------------------------------------------------- section 1
SECTION1 = ROOT / "sections" / "section1" / "export"


def export_section1() -> None:
    """Section 1 (teammate pipeline in sections/section1): FDI vs deprivation by London sub-area."""
    areas = pd.read_csv(SECTION1 / "section1_areas.csv")
    trend = pd.read_csv(SECTION1 / "section1_trend.csv")
    boroughs = pd.read_csv(SECTION1 / "section1_boroughs.csv")
    headlines = json.loads((SECTION1 / "headlines.json").read_text())
    keep = [
        "lad24cd", "lad24nm", "itl2_cd", "itl2_name", "lsoa_count", "lsoas_london_worst20",
        "dep_pct_london", "dep_pct_england", "london_overall_rank", "area_fdi_share_2024_25",
        "area_projects_2024_25", "area_new_jobs_2024_25", "area_projects_per_100_lsoas",
    ]
    _write(
        "section1.json",
        {
            "headlines": headlines,
            "areas": areas.to_dict(orient="records"),
            "trend": trend.to_dict(orient="records"),
            "boroughs": boroughs[keep].to_dict(orient="records"),
        },
    )


# --------------------------------------------------------------------------- section 2
# Team wording: "migrants" rather than "arrivals" in displayed text (data columns unchanged).
S2_WORDING = [("arrivals from abroad", "migrants from abroad"), ("new arrivals", "new migrants"),
              ("new arrival", "new migrant"), ("arrivals", "migrants")]


def _reword(obj, pairs):
    if isinstance(obj, dict):
        return {k: (_reword(v, pairs) if k != "values" else v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_reword(v, pairs) for v in obj]
    if isinstance(obj, str):
        for a, b in pairs:
            obj = obj.replace(a, b)
    return obj


SECTION2 = ROOT / "sections" / "section2" / "export"


def export_section2() -> None:
    """Section 2 (teammate pipeline in sections/section2): arrivals vs approved new-home schemes."""
    areas = pd.read_csv(SECTION2 / "section2_areas.csv")
    boroughs = pd.read_csv(SECTION2 / "section2_boroughs.csv")
    wards = pd.read_csv(SECTION2 / "section2_canary_wharf_wards.csv")
    headlines = _reword(json.loads((SECTION2 / "headlines.json").read_text()), S2_WORDING)
    cw = wards[wards["canary_wharf_cluster"]]
    keep = [
        "lad24cd", "lad24nm", "itl2_name", "residents_2021", "arrived_from_abroad", "arrived_from_abroad_per_1000",
        "new_arrivals_per_1000", "new_home_applications", "new_home_approved", "new_home_approval_rate",
        "new_homes_approved_per_1000_arrivals", "new_home_median_days", "pct_approved_new_homes_affordable",
        "pct_approved_new_homes_tall_building", "pct_approved_new_homes_build_to_rent",
    ]
    _write(
        "section2.json",
        {
            "headlines": headlines,
            "areas": areas.to_dict(orient="records"),
            "boroughs": boroughs[keep].to_dict(orient="records"),
            "canary_wharf": {
                "wards": cw["ward_name"].tolist(),
                "new_home_applications": int(cw["new_home_applications"].sum()),
                "new_home_approved": int(cw["new_home_approved"].sum()),
                "new_home_decided": int(cw["new_home_decided"].sum()),
            },
        },
    )


# --------------------------------------------------------------------------- section 3
INDICATORS = [
    # (column, label, higher_is_worse)
    ("income_score", "Income deprivation", True),
    ("employment_score", "Employment deprivation", True),
    ("education_skills_and_training_score", "Education & skills deprivation", True),
    ("health_deprivation_and_disability_score", "Health deprivation", True),
    ("crime_score", "Crime", True),
    ("living_environment_score", "Poor living environment", True),
    ("geographical_barriers_sub_domain_score", "Distance to services", True),
    ("wider_barriers_sub_domain_score", "Housing stress (overcrowding, affordability)", True),
    ("pct_older_60_plus", "Share aged 60+", None),
    ("bf_max_dwellings_per_1k_pop", "Brownfield homes per 1,000 residents", None),
]


def export_section3(demand: str) -> None:
    m = classify("london", demand)
    meta = {
        "scope": "London",
        "demand": m.attrs["demand"],
        "demand_label": m.attrs["demand_label"],
        "split": "median within London",
        "groups": GROUP_LABELS,
        "n_msoas": int(len(m)),
    }

    # Map layer
    geo = msoa_geometries().merge(
        m[
            [
                "msoa21cd", "msoa21nm", "lad24nm", "group", "deprivation_index", "demand_index",
                "index_of_multiple_deprivation_score", "total_population_mid_2022",
                "bf_sites", "bf_max_dwellings", "bf_sites_missing_dwellings", "bf_hectares",
            ]
        ],
        on="msoa21cd",
    )
    num = geo.select_dtypes("number").columns
    geo[num] = geo[num].round(3)
    _write("section3_msoa.geojson", _geojson(geo))

    # Group profile: each indicator z-scored across London MSOAs, then averaged per group.
    rows = []
    for col, label, worse in INDICATORS:
        z = (m[col] - m[col].mean()) / m[col].std(ddof=0)
        means = z.groupby(m["group"]).mean()
        raw = m.groupby("group")[col].mean()
        rows.append(
            {
                "key": col, "label": label, "higher_is_worse": worse,
                "z": {g: means.get(g) for g in GROUP_LABELS},
                "raw": {g: raw.get(g) for g in GROUP_LABELS},
            }
        )

    g = m.groupby("group")
    summary = pd.DataFrame(
        {
            "n_msoas": g.size(),
            "population": g["total_population_mid_2022"].sum(),
            "bf_sites": g["bf_sites"].sum(),
            "bf_max_dwellings": g["bf_max_dwellings"].sum(),
            "bf_sites_missing_dwellings": g["bf_sites_missing_dwellings"].sum(),
        }
    )
    summary["bf_homes_per_1k"] = summary["bf_max_dwellings"] / summary["population"] * 1000

    candidates = (
        m[m["group"] == "C"]
        .sort_values("bf_max_dwellings", ascending=False)
        .head(15)[
            ["msoa21cd", "msoa21nm", "lad24nm", "deprivation_index", "demand_index",
             "bf_sites", "bf_max_dwellings", "bf_sites_missing_dwellings"]
        ]
    )

    _write(
        "section3.json",
        {
            "meta": meta,
            "summary": summary.reset_index().to_dict(orient="records"),
            "profile": rows,
            "candidates": candidates.to_dict(orient="records"),
        },
    )


# --------------------------------------------------------------------------- interactive app
# Opportunity-score criteria: (key, source column, higher_is_better). Each becomes a 0-1
# percentile within London so the browser can re-weight them instantly.
CRITERIA = [
    ("need", "deprivation_index", True),
    ("land", "bf_max_dwellings_per_1k_pop", True),
    ("room", "demand_index", False),
    ("work", "pct_working_age_18_66", True),
    ("access", "geographical_barriers_sub_domain_score", False),
    ("underinv", "area_projects_per_100_lsoas", False),
]


def export_app(demand: str) -> None:
    m = classify("london", demand)
    attrs = dict(m.attrs)  # merge() drops attrs
    s1 = pd.read_csv(SECTION1 / "section1_boroughs.csv")
    m = m.merge(
        s1[["lad24cd", "itl2_cd", "itl2_name", "area_projects_per_100_lsoas", "area_fdi_share_2024_25",
            "dep_pct_london"]],
        on="lad24cd", how="left", validate="m:1",
    )
    assert m["itl2_cd"].notna().all()
    for key, col, up in CRITERIA:
        m[f"p_{key}"] = m[col].rank(pct=True, ascending=up)

    cols = {
        "msoa21cd": "id", "msoa21nm": "name", "lad24cd": "bcode", "lad24nm": "borough",
        "itl2_name": "area", "group": "group", "total_population_mid_2022": "pop",
        "deprivation_index": "dep", "demand_index": "pressure", "bf_sites": "bf_sites",
        "bf_max_dwellings": "bf_homes", "bf_max_dwellings_per_1k_pop": "bf_per1k",
        "pct_working_age_18_66": "working", "income_score": "income", "employment_score": "employment",
        "area_projects_per_100_lsoas": "fdi_per100", "area_fdi_share_2024_25": "fdi_share",
        **{f"p_{k}": f"p_{k}" for k, _, _ in CRITERIA},
    }
    geo = msoa_geometries().merge(m[list(cols)], on="msoa21cd").rename(columns=cols)
    num = geo.select_dtypes("number").columns
    geo[num] = geo[num].round(3)
    _write("app_msoa.geojson", _geojson(geo))

    b = load_borough_boundaries().merge(
        s1.rename(columns={"lad24cd": "code"})[
            ["code", "itl2_name", "dep_pct_london", "london_overall_rank", "area_projects_per_100_lsoas",
             "area_fdi_share_2024_25", "area_projects_2024_25", "lsoas_london_worst20", "lsoa_count"]
        ],
        on="code",
    )
    c = b.to_crs(27700).representative_point().to_crs(4326)
    b["lon"], b["lat"] = c.x.round(4), c.y.round(4)
    _write("app_boroughs.geojson", _geojson(b))
    _write(
        "app_meta.json",
        {
            "demand": attrs["demand"], "demand_label": attrs["demand_label"],
            "groups": GROUP_LABELS,
            "s1_headline": json.loads((SECTION1 / "headlines.json").read_text())["primary"]["text"],
        },
    )


if __name__ == "__main__":
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    print("Exporting web data:")
    export_boroughs()
    export_section1()
    export_section2()
    # Demand axis: IoD 2025 wider-barriers (unmet housing demand). WhereToBuild is not used:
    # the only copy available was corrupted by a spreadsheet export (see classify.py).
    export_section3("proxy")
    export_app("proxy")
