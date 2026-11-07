"""Step 4: export Section 2 in the team's shared format.

Every table is keyed on an area code so it joins with Section 1 and the other sections:
  lad24cd  = borough (Local Authority District 2024 code)
  itl2_cd  = London sub-area (ITL2 code)

Reads  clean/
Writes export/section2_boroughs.csv, export/section2_areas.csv, export/section2_yearly.csv,
       export/section2_canary_wharf_wards.csv, export/headlines.json, export/SOURCES.md

Run from the Section2_Pipeline folder:  python3 scripts/04_export.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN, OUT = ROOT / "clean", ROOT / "export"
OUT.mkdir(exist_ok=True)

boroughs = pd.read_csv(CLEAN / "boroughs.csv").drop(columns=["dep_pct_london", "london_housing_rank"])  # these live in Section 1
areas = pd.read_csv(CLEAN / "areas.csv")
yearly = pd.read_csv(CLEAN / "yearly.csv")
wards = pd.read_csv(CLEAN / "canary_wharf_wards.csv")

assert boroughs["lad24cd"].str.match(r"^E09\d{6}$").all() and boroughs["lad24cd"].is_unique
boroughs.to_csv(OUT / "section2_boroughs.csv", index=False)
areas.to_csv(OUT / "section2_areas.csv", index=False)
yearly.to_csv(OUT / "section2_yearly.csv", index=False)
wards.to_csv(OUT / "section2_canary_wharf_wards.csv", index=False)

inner = areas[areas["itl2_name"].str.startswith("Inner")]
outer = areas[~areas["itl2_name"].str.startswith("Inner")]
pace_inner = inner["new_home_approved"].sum() / inner["new_arrivals"].sum() * 1000
pace_outer = outer["new_home_approved"].sum() / outer["new_arrivals"].sum() * 1000
cw = wards[wards["canary_wharf_cluster"]]
top = boroughs.nlargest(1, "arrived_from_abroad_per_1000").iloc[0]
headlines = {
    "primary": {
        "text": (f"Inner London takes {inner['fdi_share_2024_25'].sum():.0f}% of FDI projects and "
                 f"{inner['share_of_london_arrivals_from_abroad'].sum():.0f}% of arrivals from abroad, but only "
                 f"{inner['share_of_london_new_home_approvals'].sum():.0f}% of approved new-home schemes"),
        "values": {"inner_fdi_share_pct": round(inner["fdi_share_2024_25"].sum(), 1),
                   "inner_arrivals_from_abroad_share_pct": round(inner["share_of_london_arrivals_from_abroad"].sum(), 1),
                   "inner_new_home_approvals_share_pct": round(inner["share_of_london_new_home_approvals"].sum(), 1)}},
    "secondary": {
        "text": (f"Inner London approves {pace_inner:.1f} new-home schemes per 1,000 new arrivals; "
                 f"outer London approves {pace_outer:.1f} (about {pace_outer / pace_inner:.0f}x more)"),
        "values": {"inner_schemes_per_1000_arrivals": round(pace_inner, 1), "outer_schemes_per_1000_arrivals": round(pace_outer, 1)}},
    "supporting": [
        f"{top.lad24nm} had the highest arrivals from abroad: {top.arrived_from_abroad_per_1000} per 1,000 residents",
        f"Inner West approves {areas.set_index('itl2_name').loc['Inner West', 'new_home_approval_rate']}% of decided new-home "
        f"schemes (highest), so the gap is fewer schemes coming forward, not more refusals",
        f"Canary Wharf cluster (5 Tower Hamlets wards): {int(cw['new_home_applications'].sum())} new-home applications, "
        f"{int(cw['new_home_approved'].sum())} approved, 2021-25",
    ],
    "charts_for_web_app": [
        "Grouped bar per sub-area: fdi_share_2024_25 (blue), share_of_london_arrivals_from_abroad (orange), "
        "share_of_london_new_home_approvals (green). Data: section2_areas.csv",
        "Choropleth: boroughs shaded by arrived_from_abroad_per_1000 or new_homes_approved_per_1000_arrivals. Data: section2_boroughs.csv",
        "Scatter: arrived_from_abroad_per_1000 (x) vs new_homes_approved_per_1000_arrivals (y), coloured by area_fdi_share_2024_25",
    ],
    "caveats": [
        "Counts planning schemes, not individual homes (dwelling numbers are filled for under 1 in 10 schemes)",
        "Council portals record applications differently, so rates are more reliable than raw counts",
        "Migration is one year before Census 2021 (during COVID-19); planning is 2021-25",
        "Housing-type figures come from words in descriptions, not official tenure data",
    ],
}
(OUT / "headlines.json").write_text(json.dumps(headlines, indent=2))

(OUT / "SOURCES.md").write_text("""# Section 2 sources

| Dataset | Publisher | Used for |
|---|---|---|
| Census 2021 MIG001: migrant inflow by lower-tier local authority | Office for National Statistics | Who moved into each borough in the year before the census, from abroad, the rest of the UK and the rest of London |
| London planning applications 2015-2025 (file: foundations_london_housing_2015_2025) | Compiled from London planning authority portals (each row links to its council record) | New-home schemes, approvals, decision times, housing types mentioned |
| Section 1 export (section1_boroughs.csv, section1_areas.csv) | This project, from DBT Inward Investment Results 2025-26 and MHCLG IoD 2025 | FDI share by sub-area; borough-to-sub-area mapping |
| Local Authority District boundaries | ONS, via github.com/martinjc/UK-GeoJSON | Map shapes; placing development-corporation applications in boroughs |

ONS, DBT and MHCLG data under the Open Government Licence v3.0. Boundaries: contains National Statistics and OS data © Crown copyright and database right.

Notes for the methods section:
- New-home schemes are identified from application descriptions (new build, conversion or change of use creating homes), excluding follow-up applications (conditions, amendments) and householder extensions.
- Rates use decided applications only (approved or refused); withdrawn and undecided are excluded.
- Old Oak and Park Royal and London Legacy development corporation applications are placed in boroughs by their coordinates.
- Association, not causation.
""")
print(f"Exported {len(boroughs)} boroughs (key: lad24cd), {len(areas)} sub-areas (key: itl2_cd) to export/")
print(json.dumps(headlines["primary"]["text"]), json.dumps(headlines["secondary"]["text"]))
