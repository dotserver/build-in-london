"""Step 1: clean planning and migration data into tidy Section 2 tables.

Question: in the areas where FDI concentrates (e.g. Canary Wharf), is new housing keeping
pace with migration, and what kind of housing is being approved?

Reads  raw/   (original downloads + Section 1's export, untouched)
Writes clean/ (boroughs.csv, areas.csv, canary_wharf_wards.csv, yearly.csv, map_data.json)

Run from the Section2_Pipeline folder:  python3 scripts/01_clean.py
"""
import json
import math
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW, CLEAN = ROOT / "raw", ROOT / "clean"
CLEAN.mkdir(exist_ok=True)

# ------------------------------------------------------------ boundaries
geo = json.loads((RAW / "lad_boundaries_ons.geojson").read_text())
LONDON = {f["properties"]["LAD13CD"]: f for f in geo["features"] if f["properties"]["LAD13CD"].startswith("E09")}
NAME_TO_CODE = {f["properties"]["LAD13NM"]: c for c, f in LONDON.items()}


def polygons(feature):
    g = feature["geometry"]
    return [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]


def inside(lon, lat, poly):
    """Ray casting on the outer ring of one polygon."""
    ring, hit = poly[0], False
    for (x1, y1, *_), (x2, y2, *_) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def borough_at(lon, lat):
    for code, f in LONDON.items():
        if any(inside(lon, lat, p) for p in polygons(f)):
            return code
    return None


# --------------------------------------------------------- planning data
plan = pd.read_csv(RAW / "london_planning_applications_2015_2025.csv.gz", low_memory=False)
log = {"rows_raw": len(plan)}

# 1. Planning authority names -> official borough codes.
#    Development corporations (Old Oak Park Royal, London Legacy) span several boroughs,
#    so their applications are placed by their coordinates.
ALIASES = {"Kensington": "Kensington and Chelsea", "Kingston": "Kingston upon Thames",
           "Richmond": "Richmond upon Thames", "City": "City of London"}
plan["lad24cd"] = plan["area_name"].replace(ALIASES).map(NAME_TO_CODE)
dev_corp = plan["lad24cd"].isna() & plan["lat"].notna()
plan.loc[dev_corp, "lad24cd"] = [borough_at(lon, lat) for lon, lat in plan.loc[dev_corp, ["lng", "lat"]].itertuples(index=False)]
log["dev_corp_rows_placed_by_coordinates"] = int(dev_corp.sum())
plan = plan[plan["lad24cd"].notna()]

# 2. Keep 2021-2025: before 2021 only one borough has any records (146 rows), so earlier years aren't comparable
plan["year"] = pd.to_numeric(plan["start_date"].str[:4], errors="coerce")
log["rows_dropped_pre_2021"] = int((plan["year"] < 2021).sum())
plan = plan[plan["year"].between(2021, 2025)]

# 3. Remove exact duplicates (same borough, reference)
before = len(plan)
plan = plan.drop_duplicates(["lad24cd", "uid"])
log["duplicate_rows_removed"] = before - len(plan)

# 4. Classify new-home schemes from the description text.
#    The dataset's app_type and app_size labels vary by council portal (e.g. condition discharges tagged "Full"),
#    so new-build housing is identified from what the application actually proposes.
desc = plan["description"].fillna("").str.lower()
FOLLOW_UP = (r"pursuant to|discharge|details of|non[- ]material|amendment|section 96|s96a|s73|variation of condition|"
             r"removal of condition|approval of details|reserved matters|condition\s?\d|minor material|lawful|certificate|"
             r"prior approval|observations|consultation|tree|advert")
NEW_BUILD = r"erection of|construction of|redevelopment|demolition|conversion of|change of use"
HOMES = r"dwelling|flats?\b|residential units?|new homes|apartments|houses|class c3|residential"
HOUSEHOLDER = (r"single storey|rear extension|loft|dormer|outbuilding|garage|porch|side extension|ground floor extension|"
               r"roof extension|householder|conservatory|summer ?house|annex")
plan["new_homes"] = (desc.str.contains(NEW_BUILD) & desc.str.contains(HOMES)
                     & ~desc.str.contains(FOLLOW_UP) & ~desc.str.contains(HOUSEHOLDER))

# 5. Outcome: decided = approved or refused (withdrawn / undecided are excluded from rates)
plan["approved"] = plan["status"].isin(["Permitted", "Conditions"])
plan["refused"] = plan["status"].eq("Rejected")
plan["decided"] = plan["approved"] | plan["refused"]

# 6. Housing type mentioned in approved new-home schemes (text flags, not official tenure data)
FLAGS = {"affordable": r"affordable|social rent|shared ownership|london living rent",
         "student": r"student",
         "build_to_rent": r"build[- ]to[- ]rent|\bbtr\b",
         "co_living": r"co-?living|shared living|large[- ]scale purpose[- ]built",
         "tall_building": r"(?:1\d|[2-9]\d)\s*(?:-|to)?\s*storey|tower"}  # 10+ storeys
for k, pattern in FLAGS.items():
    plan[f"mentions_{k}"] = desc.str.contains(pattern)

# n_dwellings is filled for only ~1 in 5 new-home schemes and repeats across follow-up applications,
# so dwelling totals are not used for comparisons.
nh = plan[plan["new_homes"]]
log["n_dwellings_coverage_new_homes"] = round(float(nh["n_dwellings"].notna().mean()), 3)
log["rows_clean"] = len(plan)
log["new_home_applications"] = int(plan["new_homes"].sum())


def summarise(df, keys):
    g = df.groupby(keys)
    out = pd.DataFrame({
        "planning_applications": g.size(),
        "new_home_applications": g["new_homes"].sum(),
        "new_home_decided": g.apply(lambda x: (x.new_homes & x.decided).sum(), include_groups=False),
        "new_home_approved": g.apply(lambda x: (x.new_homes & x.approved).sum(), include_groups=False),
        "all_approved": g["approved"].sum(), "all_decided": g["decided"].sum(),
        "new_home_median_days": g.apply(lambda x: x.loc[x.new_homes & x.decided, "days_to_decision"].median(), include_groups=False),
    })
    for k in FLAGS:
        out[f"pct_approved_new_homes_{k}"] = g.apply(
            lambda x, k=k: x.loc[x.new_homes & x.approved, f"mentions_{k}"].mean() * 100, include_groups=False).round(1)
    out["new_home_approval_rate"] = (out["new_home_approved"] / out["new_home_decided"] * 100).round(1)
    out["overall_approval_rate"] = (out["all_approved"] / out["all_decided"] * 100).round(1)
    return out.reset_index()


boroughs = summarise(plan, "lad24cd")
yearly = summarise(plan, ["lad24cd", "year"])

# ------------------------------------------------------- migration (Census 2021)
mig = pd.read_csv(RAW / "census2021_mig001_ltla_inflow.csv")
mig.columns = ["lad24cd", "lad24nm", "cat_code", "category", "sex_code", "sex", "age_code", "age", "count"]
mig = mig[mig["lad24cd"].str.startswith("E09")]
CATS = {"Lived at the same address one year ago": "same_address",
        "Inflow: lived elsewhere one year ago, but within the same area": "moved_within_borough",
        "Inflow: lived elsewhere one year ago outside the area, but within the associated area": "arrived_from_rest_of_london",
        "Inflow: lived elsewhere one year ago outside the associated area, but within the UK": "arrived_from_rest_of_uk",
        "Inflow: lived elsewhere one year ago outside the UK": "arrived_from_abroad"}
mig = mig[mig["category"].isin(CATS)].assign(category=lambda m: m["category"].map(CATS))
mig = mig.pivot_table(index=["lad24cd", "lad24nm"], columns="category", values="count", aggfunc="sum").reset_index()
mig["residents_2021"] = mig[list(CATS.values())].sum(axis=1)
mig["new_arrivals"] = mig["arrived_from_abroad"] + mig["arrived_from_rest_of_uk"]  # new to London in the year
for c in ["arrived_from_abroad", "arrived_from_rest_of_uk", "arrived_from_rest_of_london", "new_arrivals"]:
    mig[f"{c}_per_1000"] = (mig[c] / mig["residents_2021"] * 1000).round(1)

# --------------------------------------------------------------- combine
s1 = pd.read_csv(RAW / "section1_boroughs.csv")[["lad24cd", "itl2_cd", "itl2_name", "dep_pct_london",
                                                  "area_fdi_share_2024_25", "london_housing_rank"]]
boroughs = mig.merge(boroughs, on="lad24cd", how="left").merge(s1, on="lad24cd", how="left")
boroughs["new_homes_approved_per_10k_residents"] = (boroughs["new_home_approved"] / boroughs["residents_2021"] * 1e4).round(2)
boroughs["new_homes_approved_per_1000_arrivals"] = (boroughs["new_home_approved"] / boroughs["new_arrivals"] * 1000).round(2)
assert len(boroughs) == 33 and boroughs["itl2_cd"].notna().all()

s1_areas = pd.read_csv(RAW / "section1_areas.csv")[["itl2_cd", "fdi_share_2024_25", "jobs_share_2024_25"]]
areas = (boroughs.groupby(["itl2_cd", "itl2_name"])
         [["residents_2021", "arrived_from_abroad", "arrived_from_rest_of_uk", "new_arrivals", "new_home_approved",
           "new_home_decided"]].sum().reset_index().merge(s1_areas, on="itl2_cd"))
for c, label in [("arrived_from_abroad", "share_of_london_arrivals_from_abroad"),
                 ("new_arrivals", "share_of_london_new_arrivals"),
                 ("new_home_approved", "share_of_london_new_home_approvals")]:
    areas[label] = (areas[c] / areas[c].sum() * 100).round(1)
areas["arrivals_from_abroad_per_1000"] = (areas["arrived_from_abroad"] / areas["residents_2021"] * 1000).round(1)
areas["new_homes_approved_per_1000_arrivals"] = (areas["new_home_approved"] / areas["new_arrivals"] * 1000).round(2)
areas["new_home_approval_rate"] = (areas["new_home_approved"] / areas["new_home_decided"] * 100).round(1)

# --------------------------------------------- Canary Wharf: Tower Hamlets wards
CW = ["Canary Wharf", "Blackwall and Cubitt Town", "Island Gardens", "Poplar", "Limehouse"]
th = plan[plan["lad24cd"] == NAME_TO_CODE["Tower Hamlets"]].copy()
th["canary_wharf_cluster"] = th["ward_name"].isin(CW)
wards = summarise(th, ["ward_name", "canary_wharf_cluster"]).sort_values("planning_applications", ascending=False)

boroughs = boroughs.sort_values("arrived_from_abroad_per_1000", ascending=False)
boroughs.to_csv(CLEAN / "boroughs.csv", index=False)
areas.to_csv(CLEAN / "areas.csv", index=False)
yearly.to_csv(CLEAN / "yearly.csv", index=False)
wards.to_csv(CLEAN / "canary_wharf_wards.csv", index=False)
(CLEAN / "cleaning_log.json").write_text(json.dumps(log, indent=2))

# ------------------------------------------------------------- map shapes
k = math.cos(math.radians(51.5))
rings = {c: [[(lon * k, -lat) for lon, lat, *_ in r] for p in polygons(f) for r in p] for c, f in LONDON.items()}
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


def clean_val(v):
    return None if pd.isna(v) else (round(float(v), 2) if isinstance(v, float) else int(v) if not isinstance(v, str) else v)


map_cols = ["lad24cd", "lad24nm", "itl2_cd", "itl2_name", "residents_2021", "arrived_from_abroad", "arrived_from_rest_of_uk",
            "arrived_from_rest_of_london", "arrived_from_abroad_per_1000", "new_arrivals_per_1000", "new_home_applications",
            "new_home_approved", "new_home_approval_rate", "new_home_median_days", "new_homes_approved_per_10k_residents",
            "new_homes_approved_per_1000_arrivals", "overall_approval_rate", "dep_pct_london", "area_fdi_share_2024_25"] + \
           [f"pct_approved_new_homes_{k}" for k in FLAGS]
map_data = {"w": 1000, "h": round((max(ys) - min(ys)) * scale, 1), "paths": paths,
            "boroughs": [{c: clean_val(r[c]) for c in map_cols} for _, r in boroughs.iterrows()],
            "areas": {r["itl2_cd"]: {c: clean_val(r[c]) for c in areas.columns} for _, r in areas.iterrows()}}
(CLEAN / "map_data.json").write_text(json.dumps(map_data, separators=(",", ":")))

print(json.dumps(log, indent=2))
print(areas[["itl2_name", "fdi_share_2024_25", "share_of_london_arrivals_from_abroad", "share_of_london_new_home_approvals",
             "new_homes_approved_per_1000_arrivals"]].to_string(index=False))
