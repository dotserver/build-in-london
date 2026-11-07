"""Step 1: clean the raw datasets into tidy Section 1 tables.

Reads  raw/   (original downloads, untouched)
Writes clean/ (boroughs.csv, areas.csv, london_trend.csv, map_data.json)

Run from the Section1_Pipeline folder:  python3 scripts/01_clean.py
"""
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW, CLEAN = ROOT / "raw", ROOT / "clean"
CLEAN.mkdir(exist_ok=True)

# London's five ITL2 sub-areas (2021 boundaries) and the boroughs in each.
# DBT publishes FDI only at this level, so boroughs are grouped to match.
AREAS = {
    "TLI3": ("Inner West", ["City of London", "Camden", "Westminster", "Kensington and Chelsea",
                            "Hammersmith and Fulham", "Wandsworth"]),
    "TLI4": ("Inner East", ["Hackney", "Tower Hamlets", "Newham", "Islington", "Haringey",
                            "Lambeth", "Southwark", "Lewisham"]),
    "TLI5": ("Outer East & NE", ["Barking and Dagenham", "Havering", "Redbridge", "Waltham Forest",
                                 "Enfield", "Bexley", "Greenwich"]),
    "TLI6": ("Outer South", ["Bromley", "Croydon", "Merton", "Kingston upon Thames", "Sutton"]),
    "TLI7": ("Outer West & NW", ["Barnet", "Brent", "Ealing", "Harrow", "Hillingdon", "Hounslow",
                                 "Richmond upon Thames"]),
}
BOROUGH_TO_AREA = {b: code for code, (_, names) in AREAS.items() for b in names}

RANKS = {  # long IMD column names -> short names
    "Index of Multiple Deprivation (IMD) Rank (where 1 is most deprived)": "overall",
    "Income - Rank (where 1 is most deprived)": "income",
    "Employment - Rank (where 1 is most deprived)": "employment",
    "Education, Skills and Training - Rank (where 1 is most deprived)": "education",
    "Health Deprivation and Disability - Rank (where 1 is most deprived)": "health",
    "Crime - Rank (where 1 is most deprived)": "crime",
    "Barriers to Housing and Services - Rank (where 1 is most deprived)": "housing",
    "Living Environment - Rank (where 1 is most deprived)": "environment",
    "IDACI - Rank (where 1 is most deprived)": "child_poverty",
    "IDAOPI - Rank (where 1 is most deprived)": "older_poverty",
}


def to_number(value):
    """DBT marks suppressed cells '[c]' and missing ones '-': keep them as blanks, not zeros."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- deprivation
lsoa = pd.read_csv(RAW / "imd2025_lsoa.csv")
lsoa.columns = ["lsoa", "lsoa_name", "lad", "borough", "imd_rank", "imd_decile"]

# Keep London only: borough codes start with E09
london = lsoa[lsoa["lad"].str.startswith("E09")].copy()

# London-vs-London yardstick: the most deprived 20% of London's own neighbourhoods
london["london_rank"] = london["imd_rank"].rank(method="first")  # 1 = most deprived in London
london["london_worst20"] = london["london_rank"] <= len(london) * 0.2
london["england_worst20"] = london["imd_decile"] <= 2

boroughs = (london.groupby(["lad", "borough"])
            .agg(lsoas=("lsoa", "size"),
                 london_worst20=("london_worst20", "sum"),
                 england_worst20=("england_worst20", "sum"))
            .reset_index())
boroughs["dep_pct_london"] = (boroughs["london_worst20"] / boroughs["lsoas"] * 100).round(1)
boroughs["dep_pct_england"] = (boroughs["england_worst20"] / boroughs["lsoas"] * 100).round(1)

# Borough-level ranks: England rank (1-296) and London rank (1-33)
summary = pd.read_csv(RAW / "imd2025_local_authority_summaries.csv")
summary.columns = [c.strip() for c in summary.columns]
summary = summary.rename(columns={"Local Authority District code (2024)": "lad", **{k.strip(): v for k, v in RANKS.items()}})
summary = summary[["lad"] + list(RANKS.values())]
boroughs = boroughs.merge(summary, on="lad", how="left")
for r in RANKS.values():
    boroughs[f"london_{r}_rank"] = boroughs[r].rank(method="min").astype(int)
    boroughs = boroughs.rename(columns={r: f"england_{r}_rank"})

boroughs["area_code"] = boroughs["borough"].map(BOROUGH_TO_AREA)
boroughs["area"] = boroughs["area_code"].map(lambda c: AREAS[c][0])
assert len(boroughs) == 33 and boroughs["area_code"].notna().all(), "every borough must map to a sub-area"
boroughs = boroughs.sort_values("dep_pct_london", ascending=False)

# ------------------------------------------------------------------------ FDI
dbt = pd.read_excel(RAW / "dbt-inward-investment-results-tables-2025-to-2026.ods", engine="odf",
                    sheet_name=["4_1", "4_12"], header=None)
YEARS = ["2023-24", "2024-25", "2025-26"]

# Table 4.12: ITL2 rows. Columns: name, code, then (projects, new jobs, safe jobs) per year
itl2 = dbt["4_12"]
itl2 = itl2[itl2[1].astype(str).str.startswith("TLI")].set_index(1)
fdi = pd.DataFrame({"area_code": list(AREAS)})
for i, year in enumerate(YEARS):
    fdi[f"projects_{year}"] = [to_number(itl2.loc[c, 2 + 3 * i]) for c in AREAS]
    fdi[f"new_jobs_{year}"] = [to_number(itl2.loc[c, 3 + 3 * i]) for c in AREAS]

# Table 4.1: London totals (denominator for the trend; includes areas DBT suppressed)
t41 = dbt["4_1"]
london_row = t41[t41[0] == "London"].iloc[0]
trend = pd.DataFrame({"year": YEARS,
                      "london_projects": [to_number(london_row[i]) for i in (1, 2, 3)],
                      "london_new_jobs": [to_number(london_row[i]) for i in (4, 5, 6)]})
inner_west, inner_east = fdi.set_index("area_code").loc["TLI3"], fdi.set_index("area_code").loc["TLI4"]
trend["inner_west_share"] = [round(inner_west[f"projects_{y}"] / p * 100, 1) for y, p in zip(YEARS, trend["london_projects"])]
trend["inner_east_share"] = [round(inner_east[f"projects_{y}"] / p * 100, 1) for y, p in zip(YEARS, trend["london_projects"])]
trend["inner_west_jobs_share"] = [round(inner_west[f"new_jobs_{y}"] / j * 100, 1) for y, j in zip(YEARS, trend["london_new_jobs"])]

# ---------------------------------------------------------- combine by area
# 2024-25 is the only year DBT publishes for all five sub-areas, so shares use it
areas = (boroughs.groupby("area_code")
         .agg(lsoas=("lsoas", "sum"), london_worst20=("london_worst20", "sum"))
         .reset_index()
         .merge(fdi, on="area_code"))
areas.insert(1, "area", areas["area_code"].map(lambda c: AREAS[c][0]))
areas["deprivation_share"] = (areas["london_worst20"] / areas["london_worst20"].sum() * 100).round(1)
areas["fdi_share_2024-25"] = (areas["projects_2024-25"] / areas["projects_2024-25"].sum() * 100).round(1)
areas["jobs_share_2024-25"] = (areas["new_jobs_2024-25"] / areas["new_jobs_2024-25"].sum() * 100).round(1)
areas["projects_per_100_lsoas"] = (areas["projects_2024-25"] / areas["lsoas"] * 100).round(1)

boroughs.to_csv(CLEAN / "boroughs.csv", index=False)
areas.to_csv(CLEAN / "areas.csv", index=False)
trend.to_csv(CLEAN / "london_trend.csv", index=False)

# --------------------------------------------------------------- map shapes
# Project borough boundaries (lon/lat) to a flat 1000px-wide SVG and drop points under ~1px apart
geo = json.loads((RAW / "lad_boundaries_ons.geojson").read_text())
features = [f for f in geo["features"] if f["properties"]["LAD13CD"].startswith("E09")]
k = math.cos(math.radians(51.5))
rings = {}
for f in features:
    g = f["geometry"]
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
    rings[f["properties"]["LAD13CD"]] = [[(lon * k, -lat) for lon, lat, *_ in r] for poly in polys for r in poly]
xs = [x for rs in rings.values() for r in rs for x, _ in r]
ys = [y for rs in rings.values() for r in rs for _, y in r]
scale = 1000 / (max(xs) - min(xs))
paths = {}
for code, rs in rings.items():
    parts = []
    for r in rs:
        pts = [((x - min(xs)) * scale, (y - min(ys)) * scale) for x, y in r]
        kept = [pts[0]]
        for p in pts[1:]:
            if math.dist(p, kept[-1]) >= 1.2:
                kept.append(p)
        if len(kept) >= 3:
            parts.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in kept) + "Z")
    paths[code] = "".join(parts)
assert set(paths) == set(boroughs["lad"]), "boundaries and deprivation data must cover the same 33 boroughs"

def num(v):
    return None if pd.isna(v) else int(v)

rank_keys = list(RANKS.values())
map_data = {
    "w": 1000, "h": round((max(ys) - min(ys)) * scale, 1), "paths": paths,
    "boroughs": [{
        "code": r["lad"], "name": r["borough"], "area": r["area_code"], "n": int(r["lsoas"]),
        "lw20": int(r["london_worst20"]), "e20": int(r["england_worst20"]),
        "depPct": r["dep_pct_london"], "engPct": r["dep_pct_england"],
        "lon": {k2: int(r[f"london_{k2}_rank"]) for k2 in rank_keys},
        "eng": {k2: int(r[f"england_{k2}_rank"]) for k2 in rank_keys},
    } for _, r in boroughs.iterrows()],
    "areas": {r["area_code"]: {
        "short": r["area"], "name": r["area"], "lsoas": int(r["lsoas"]),
        "p": [num(r[f"projects_{y}"]) for y in YEARS], "j": [num(r[f"new_jobs_{y}"]) for y in YEARS],
        "fdiShare": r["fdi_share_2024-25"], "jobShare": r["jobs_share_2024-25"],
        "depShare": r["deprivation_share"], "per100": r["projects_per_100_lsoas"],
        "boroughs": sorted(AREAS[r["area_code"]][1]),
    } for _, r in areas.iterrows()},
}
# The ranks map uses these key names
for b in map_data["boroughs"]:
    for d in (b["lon"], b["eng"]):
        d["children"], d["older"] = d.pop("child_poverty"), d.pop("older_poverty")
(CLEAN / "map_data.json").write_text(json.dumps(map_data, separators=(",", ":")))

print(f"London neighbourhoods: {len(london)}  |  London's most deprived 20%: {int(london['london_worst20'].sum())}")
print(areas[["area", "fdi_share_2024-25", "deprivation_share", "projects_per_100_lsoas"]].to_string(index=False))
print(f"\nWrote {', '.join(p.name for p in sorted(CLEAN.iterdir()))} to clean/")
