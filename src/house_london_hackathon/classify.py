"""Four-group classification at MSOA level: housing demand pressure x deprivation.

Axes
----
Deprivation ("people" deprivation): population-weighted IoD 2025 domain scores for
income, employment, education/skills and health, z-scored within the chosen scope and
combined with the official IMD domain weights (22.5/22.5/13.5/13.5, renormalised).
Barriers-to-housing is deliberately excluded so it can't double-count with the demand axis.

Demand pressure:
  - "wheretobuild" (preferred): WhereToBuild tightness (demand / supply) from the MSOA CSV
    on the event Drive, placed at data/raw/wheretobuild_msoa_stats.csv.
  - "proxy" (fallback): IoD 2025 "wider barriers" sub-domain (overcrowding, homelessness,
    housing affordability). It measures housing *stress*, not search demand - label it so.

Groups use a median split within the scope (England or London):
  A  High demand + deprived      -> pressure on people already struggling
  B  High demand + not deprived  -> where people want to live (FDI hotspots likely here)
  C  Low demand + deprived       -> "left behind": the candidates for redirected investment
  D  Low demand + not deprived   -> stable
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from house_london_hackathon.data import DATA_PROCESSED, DATA_RAW



DEPRIVATION_WEIGHTS = {
    "income_score": 22.5,
    "employment_score": 22.5,
    "education_skills_and_training_score": 13.5,
    "health_deprivation_and_disability_score": 13.5,
}
PROXY_DEMAND_COL = "wider_barriers_sub_domain_score"

GROUP_LABELS = {
    "A": "A: High demand + deprived",
    "B": "B: High demand + not deprived",
    "C": "C: Low demand + deprived",
    "D": "D: Low demand + not deprived",
}


def _z(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std(ddof=0)


def find_wtb_file():
    """The WhereToBuild CSV in data/raw (any name starting 'wheretobuild'), or None."""
    hits = sorted(DATA_RAW.glob("wheretobuild*.csv"))
    return hits[0] if hits else None


def _load_wtb_tightness() -> pd.Series:
    """Return WhereToBuild tightness indexed by msoa21cd (column names auto-detected).

    Refuses files whose values are not plain numbers (e.g. '123.45.00' after a
    spreadsheet round-trip) rather than silently producing garbage.
    """
    path = find_wtb_file()
    wtb = pd.read_csv(path, dtype=str)
    cols = {c.lower(): c for c in wtb.columns}
    key = next(cols[c] for c in cols if c.startswith("msoa") and ("cd" in c or "code" in c))
    val = next((cols[c] for c in cols if "tight" in c), None)
    if val is None:
        raise ValueError(f"No 'tightness' column found in {path.name}: {list(wtb.columns)}")
    raw = wtb[val].dropna().str.strip()
    bad = ~raw.str.fullmatch(r"-?\d+(\.\d+)?([eE][-+]?\d+)?")
    if bad.mean() > 0.01:
        raise ValueError(
            f"{path.name}: {bad.mean():.0%} of '{val}' values are not valid numbers "
            f"(e.g. {raw[bad].iloc[0]!r}). The file looks corrupted by a spreadsheet "
            "export - re-download the original CSV."
        )
    return pd.to_numeric(wtb.set_index(key)[val], errors="coerce").rename("demand_raw")


def classify(scope: str = "london", demand: str = "auto") -> pd.DataFrame:
    """Classify MSOAs into groups A-D. scope: 'london' | 'england'. demand: 'auto'|'wheretobuild'|'proxy'."""
    msoa = pd.read_parquet(DATA_PROCESSED / "section3_msoa.parquet")
    if scope == "london":
        msoa = msoa[msoa["is_london"]].copy()

    if demand == "auto":
        demand = "wheretobuild" if find_wtb_file() else "proxy"
    if demand == "wheretobuild":
        msoa = msoa.join(_load_wtb_tightness(), on="msoa21cd")
        demand_label = "WhereToBuild tightness (demand/supply)"
    else:
        msoa["demand_raw"] = msoa[PROXY_DEMAND_COL]
        demand_label = "Unmet housing demand (IoD 2025: overcrowding, homelessness, affordability)"

    w = pd.Series(DEPRIVATION_WEIGHTS)
    z = pd.concat({c: _z(msoa[c]) for c in w.index}, axis=1)
    msoa["deprivation_index"] = z.mul(w / w.sum()).sum(axis=1)
    msoa["demand_index"] = _z(msoa["demand_raw"])

    hi_demand = msoa["demand_index"] >= msoa["demand_index"].median()
    deprived = msoa["deprivation_index"] >= msoa["deprivation_index"].median()
    msoa["group"] = np.select(
        [hi_demand & deprived, hi_demand & ~deprived, ~hi_demand & deprived],
        ["A", "B", "C"],
        default="D",
    )
    msoa.loc[msoa["demand_index"].isna(), "group"] = pd.NA
    msoa["group_label"] = msoa["group"].map(GROUP_LABELS)
    msoa.attrs.update(scope=scope, demand=demand, demand_label=demand_label)
    return msoa


PROFILE_COLS = {
    "n_msoas": ("msoa21cd", "count"),
    "population": ("total_population_mid_2022", "sum"),
    "deprivation_index": ("deprivation_index", "mean"),
    "demand_index": ("demand_index", "mean"),
    "income": ("income_score", "mean"),
    "employment": ("employment_score", "mean"),
    "education_skills": ("education_skills_and_training_score", "mean"),
    "health": ("health_deprivation_and_disability_score", "mean"),
    "crime": ("crime_score", "mean"),
    "living_env": ("living_environment_score", "mean"),
    "geog_barriers": ("geographical_barriers_sub_domain_score", "mean"),
    "pct_children": ("pct_children_0_15", "mean"),
    "pct_working_age": ("pct_working_age_18_66", "mean"),
    "pct_60_plus": ("pct_older_60_plus", "mean"),
    "bf_sites": ("bf_sites", "sum"),
    "bf_hectares": ("bf_hectares", "sum"),
    "bf_max_dwellings": ("bf_max_dwellings", "sum"),
    "bf_sites_missing_dwellings": ("bf_sites_missing_dwellings", "sum"),
}


def group_profile(msoa: pd.DataFrame) -> pd.DataFrame:
    """One row per group: size, deprivation domain means, age mix, brownfield capacity."""
    p = msoa.groupby("group_label").agg(**PROFILE_COLS)
    p["bf_max_dwellings_per_1k_pop"] = p["bf_max_dwellings"] / p["population"] * 1000
    return p


def msoa_geometries() -> gpd.GeoDataFrame:
    """MSOA polygons built by dissolving LSOA boundaries (England)."""
    lsoa = gpd.read_file(DATA_RAW / "lsoa21_boundaries_bgc.geojson")
    lsoa.columns = lsoa.columns.str.lower()
    lookup = pd.read_csv(DATA_RAW / "lookup_lsoa21_msoa21.csv")
    lookup.columns = lookup.columns.str.lower()
    g = lsoa.merge(lookup[["lsoa21cd", "msoa21cd"]], on="lsoa21cd")
    return g.dissolve(by="msoa21cd").reset_index()[["msoa21cd", "geometry"]]


def run(scope: str = "london", demand: str = "auto") -> tuple[pd.DataFrame, pd.DataFrame]:
    msoa = classify(scope, demand)
    prof = group_profile(msoa)
    tag = f"{scope}_{msoa.attrs['demand']}"
    msoa.to_csv(DATA_PROCESSED / f"groups_msoa_{tag}.csv", index=False)
    prof.to_csv(DATA_PROCESSED / f"groups_profile_{tag}.csv")
    return msoa, prof


if __name__ == "__main__":
    for scope in ("london", "england"):
        m, p = run(scope)
        print(f"\n=== {scope} | demand = {m.attrs['demand_label']} ===")
        print(p.round(3).T.to_string())
