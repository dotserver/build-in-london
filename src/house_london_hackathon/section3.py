"""Section 3: deprived areas vs. where to build.

Builds one joined table at LSOA (2021) level, plus MSOA and local-authority roll-ups:
  - English Indices of Deprivation 2025 (all domain scores/ranks/deciles + population)
  - LSOA -> MSOA lookup (ONS, Dec 2021)
  - National brownfield land register (planning.data.gov.uk), spatially joined to LSOAs

WhereToBuild (Warwick) is joined at MSOA level by `join_wheretobuild()` once the CSV
from the event Drive is placed in data/raw/. Contact WhereToBuild before publishing.
"""

from __future__ import annotations

import json
import re

import geopandas as gpd
import pandas as pd
import requests

from house_london_hackathon.data import DATA_PROCESSED, DATA_RAW, download

IOD_URL = (
    "https://assets.publishing.service.gov.uk/media/691ded56d140bbbaa59a2a7d/"
    "File_7_IoD2025_All_Ranks_Scores_Deciles_Population_Denominators.csv"
)
BROWNFIELD_URL = "https://files.planning.data.gov.uk/dataset/brownfield-land.csv"
ONS = "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services"
LOOKUP_SVC = f"{ONS}/OA_LSOA_MSOA_EW_DEC_2021_LU_v3/FeatureServer/0/query"
LSOA_BOUNDARY_SVC = (
    f"{ONS}/Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V5"
    "/FeatureServer/0/query"
)

# London LADs are E09*; handy filter for the London-focused story.
LONDON_PREFIX = "E09"


# --------------------------------------------------------------------------- helpers
def _snake(name: str) -> str:
    name = re.sub(r"\(.*?\)", "", name)  # drop "(where 1 is most deprived ...)" etc.
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    return name


def _arcgis_paged(url: str, params: dict, page: int) -> list[dict]:
    """Fetch all records from an ArcGIS FeatureServer query, page by page."""
    out, offset = [], 0
    while True:
        p = {**params, "resultOffset": offset, "resultRecordCount": page}
        r = requests.get(url, params=p, timeout=120)
        r.raise_for_status()
        data = r.json()
        feats = data.get("features", [])
        out.extend(feats)
        if len(feats) < page and not data.get("exceededTransferLimit"):
            break
        offset += len(feats)
    return out


# --------------------------------------------------------------------------- loaders
def load_iod() -> pd.DataFrame:
    path = download(IOD_URL, "iod2025_all.csv")
    df = pd.read_csv(path)
    df.columns = [_snake(c) for c in df.columns]
    df = df.rename(
        columns={
            "children_and_young_people_sub_domain_decile_where_1_is_most_deprived_10_of_lso": (
                "children_and_young_people_sub_domain_decile"
            ),
            "lsoa_code": "lsoa21cd",
            "lsoa_name": "lsoa21nm",
            "local_authority_district_code": "lad24cd",
            "local_authority_district_name": "lad24nm",
        }
    )
    return df


def load_lsoa_msoa_lookup() -> pd.DataFrame:
    path = DATA_RAW / "lookup_lsoa21_msoa21.csv"
    if not path.exists():
        feats = _arcgis_paged(
            LOOKUP_SVC,
            {
                "where": "1=1",
                "outFields": "LSOA21CD,MSOA21CD,MSOA21NM",
                "returnDistinctValues": "true",
                "orderByFields": "LSOA21CD",
                "returnGeometry": "false",
                "f": "json",
            },
            page=1000,
        )
        df = pd.DataFrame([f["attributes"] for f in feats]).drop_duplicates("LSOA21CD")
        df.to_csv(path, index=False)
    df = pd.read_csv(path)
    df.columns = df.columns.str.lower()
    return df


def load_lsoa_boundaries() -> gpd.GeoDataFrame:
    path = DATA_RAW / "lsoa21_boundaries_bgc.geojson"
    if not path.exists():
        feats = _arcgis_paged(
            LSOA_BOUNDARY_SVC,
            {
                "where": "LSOA21CD LIKE 'E%'",  # England only (IoD is England-only)
                "outFields": "LSOA21CD",
                "orderByFields": "LSOA21CD",
                "outSR": "4326",
                "f": "geojson",
            },
            page=2000,
        )
        path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    gdf = gpd.read_file(path)
    gdf.columns = gdf.columns.str.lower()
    return gdf[["lsoa21cd", "geometry"]]


MAX_PLAUSIBLE_HA = 100

_STATUS = {
    "permissioned": "permissioned",
    "planning permission": "permissioned",
    "completed": "permissioned",
    "not-permissioned": "not_permissioned",
    "non-permissioned": "not_permissioned",
    "pending-decision": "pending",
    "submitted": "pending",
}


def load_brownfield(lsoa: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Active brownfield sites (no end-date) with the LSOA each falls in."""
    path = download(BROWNFIELD_URL, "brownfield_land.csv")
    df = pd.read_csv(path, low_memory=False)
    df = df[df["end-date"].isna()].copy()  # drop sites removed from registers

    # Location: prefer the point; fall back to the polygon's representative point.
    def _wkt(col: str) -> gpd.GeoSeries:
        vals = df[col].astype(object).where(df[col].notna(), None)
        return gpd.GeoSeries.from_wkt(vals, crs=4326, on_invalid="ignore", index=df.index)

    geom, poly = _wkt("point"), _wkt("geometry")
    geom = geom.where(geom.notna(), poly.representative_point())
    sites = gpd.GeoDataFrame(df, geometry=geom.values, crs=4326)
    sites = sites[sites.geometry.notna() & ~sites.geometry.is_empty]

    status = df["planning-permission-status"].astype(str).str.strip().str.lower()
    sites["pp_status"] = status.map(_STATUS).fillna("other")
    sites["hectares"] = pd.to_numeric(sites["hectares"], errors="coerce")
    for c in ("minimum-net-dwellings", "maximum-net-dwellings"):
        sites[c] = pd.to_numeric(sites[c], errors="coerce")

    # Data quality: the median site is ~0.25 ha; values > MAX_PLAUSIBLE_HA are almost
    # certainly unit-entry errors (m2 typed as ha) and dominate totals, so null them.
    sites["hectares_suspect"] = sites["hectares"] > MAX_PLAUSIBLE_HA
    sites.loc[sites["hectares_suspect"], "hectares"] = float("nan")
    sites = sites.drop_duplicates(["organisation-entity", "reference"])

    joined = gpd.sjoin(sites, lsoa, how="inner", predicate="within")
    return joined.drop(columns="index_right")


def aggregate_brownfield(sites: gpd.GeoDataFrame) -> pd.DataFrame:
    g = sites.groupby("lsoa21cd")
    agg = pd.DataFrame(
        {
            "bf_sites": g.size(),
            "bf_hectares": g["hectares"].sum(),
            "bf_min_dwellings": g["minimum-net-dwellings"].sum(),
            "bf_max_dwellings": g["maximum-net-dwellings"].sum(),
            "bf_sites_permissioned": g["pp_status"].apply(lambda s: (s == "permissioned").sum()),
            "bf_sites_not_permissioned": g["pp_status"].apply(
                lambda s: (s == "not_permissioned").sum()
            ),
            # Report coverage so readers know when dwelling totals are undercounts.
            "bf_sites_missing_dwellings": g["maximum-net-dwellings"].apply(
                lambda s: s.isna().sum()
            ),
            "bf_sites_hectares_suspect": g["hectares_suspect"].sum(),
        }
    )
    return agg.reset_index()


# --------------------------------------------------------------------------- build
SUM_COLS = [
    "bf_sites",
    "bf_hectares",
    "bf_min_dwellings",
    "bf_max_dwellings",
    "bf_sites_permissioned",
    "bf_sites_not_permissioned",
    "bf_sites_missing_dwellings",
    "bf_sites_hectares_suspect",
]


def build_lsoa_table() -> pd.DataFrame:
    iod = load_iod()
    lookup = load_lsoa_msoa_lookup()
    lsoa_geo = load_lsoa_boundaries()
    bf = aggregate_brownfield(load_brownfield(lsoa_geo))

    t = iod.merge(lookup, on="lsoa21cd", how="left", validate="1:1")
    t = t.merge(bf, on="lsoa21cd", how="left", validate="1:1")
    t[SUM_COLS] = t[SUM_COLS].fillna(0)
    t["is_london"] = t["lad24cd"].str.startswith(LONDON_PREFIX)
    t["most_deprived_20pct"] = t["index_of_multiple_deprivation_decile"].le(2)
    t = _add_age_shares(t)
    return t


AGE_COUNTS = {
    "pct_children_0_15": "dependent_children_aged_0_15_mid_2022",
    "pct_working_age_18_66": "working_age_population_18_66_mid_2022",
    "pct_older_60_plus": "older_population_aged_60_and_over_mid_2022",
}


def _add_age_shares(t: pd.DataFrame) -> pd.DataFrame:
    for pct, col in AGE_COUNTS.items():
        t[pct] = t[col] / t["total_population_mid_2022"]
    return t


def _popweighted_rollup(t: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Population-weighted mean of domain scores + sums of brownfield capacity."""
    pop = "total_population_mid_2022"
    score_cols = [c for c in t.columns if c.endswith("_score") or c.endswith("_score_rate")]
    w = t[score_cols].multiply(t[pop], axis=0)
    w[keys] = t[keys]
    w[pop] = t[pop]
    g = w.groupby(keys, dropna=False)
    out = g[score_cols].sum().div(g[pop].sum(), axis=0)
    out[pop] = g[pop].sum()
    out[SUM_COLS] = t.groupby(keys, dropna=False)[SUM_COLS].sum()
    out["n_lsoas"] = t.groupby(keys, dropna=False).size()
    out["share_lsoas_most_deprived_20pct"] = t.groupby(keys, dropna=False)[
        "most_deprived_20pct"
    ].mean()
    out["bf_max_dwellings_per_1k_pop"] = out["bf_max_dwellings"] / out[pop] * 1000
    counts = t.groupby(keys, dropna=False)[list(AGE_COUNTS.values())].sum()
    for pct, col in AGE_COUNTS.items():
        out[pct] = counts[col] / out[pop]
    return out.reset_index()


def build_all(save: bool = True) -> dict[str, pd.DataFrame]:
    lsoa = build_lsoa_table()
    msoa = _popweighted_rollup(lsoa, ["msoa21cd", "msoa21nm", "lad24cd", "lad24nm"])
    lad = _popweighted_rollup(lsoa, ["lad24cd", "lad24nm"])
    for df in (msoa, lad):
        df["is_london"] = df["lad24cd"].str.startswith(LONDON_PREFIX)
    tables = {"section3_lsoa": lsoa, "section3_msoa": msoa, "section3_lad": lad}
    if save:
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        for name, df in tables.items():
            df.to_parquet(DATA_PROCESSED / f"{name}.parquet", index=False)
            df.to_csv(DATA_PROCESSED / f"{name}.csv", index=False)
    return tables


def join_wheretobuild(msoa: pd.DataFrame, filename: str = "wheretobuild_msoa_stats.csv"):
    """Left-join the WhereToBuild MSOA CSV (from the event Drive) onto the MSOA table."""
    wtb = pd.read_csv(DATA_RAW / filename)
    key = next(c for c in wtb.columns if c.lower().startswith("msoa") and "cd" in c.lower())
    wtb = wtb.rename(columns={key: "msoa21cd"})
    return msoa.merge(wtb, on="msoa21cd", how="left", validate="1:1")


if __name__ == "__main__":
    t = build_all()
    for k, v in t.items():
        print(k, v.shape)
