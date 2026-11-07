"""Step 4: export Section 1 in the team's shared format.

Every table is keyed on an area code so it joins with other sections:
  lad24cd  = borough (Local Authority District 2024 code, e.g. E09000025 Newham)
  itl2_cd  = London sub-area (ITL2 code, e.g. TLI4 Inner London East)

Reads  clean/
Writes export/section1_boroughs.csv, export/section1_areas.csv, export/section1_trend.csv,
       export/headlines.json, export/SOURCES.md

Run from the Section1_Pipeline folder:  python3 scripts/04_export.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN, OUT = ROOT / "clean", ROOT / "export"
OUT.mkdir(exist_ok=True)

boroughs = pd.read_csv(CLEAN / "boroughs.csv")
areas = pd.read_csv(CLEAN / "areas.csv")
trend = pd.read_csv(CLEAN / "london_trend.csv")


def snake(col):
    return col.replace("-", "_").replace(" ", "_").lower()


# Areas: one row per sub-area, keyed on itl2_cd
areas = areas.rename(columns={"area_code": "itl2_cd", "area": "itl2_name"})
areas.columns = [snake(c) for c in areas.columns]

# Boroughs: one row per borough, keyed on lad24cd.
# FDI is only published per sub-area, so each borough carries its sub-area's figures (prefixed area_).
area_cols = ["fdi_share_2024_25", "jobs_share_2024_25", "projects_2024_25", "new_jobs_2024_25",
             "projects_per_100_lsoas", "deprivation_share"]
boroughs = boroughs.rename(columns={"lad": "lad24cd", "borough": "lad24nm", "area_code": "itl2_cd", "area": "itl2_name",
                                    "lsoas": "lsoa_count", "london_worst20": "lsoas_london_worst20",
                                    "england_worst20": "lsoas_england_worst20"})
boroughs.columns = [snake(c) for c in boroughs.columns]
boroughs = boroughs.merge(areas[["itl2_cd"] + area_cols].rename(columns={c: f"area_{c}" for c in area_cols}),
                          on="itl2_cd", how="left")
first = ["lad24cd", "lad24nm", "itl2_cd", "itl2_name"]
boroughs = boroughs[first + [c for c in boroughs.columns if c not in first]]

trend.columns = [snake(c) for c in trend.columns]

assert boroughs["lad24cd"].str.match(r"^E09\d{6}$").all() and boroughs["lad24cd"].is_unique
boroughs.to_csv(OUT / "section1_boroughs.csv", index=False)
areas.to_csv(OUT / "section1_areas.csv", index=False)
trend.to_csv(OUT / "section1_trend.csv", index=False)

a = areas.set_index("itl2_name")
per_head = (a.loc["Inner West", "projects_2024_25"] / a.loc["Inner West", "lsoas"]) / \
           (a.loc["Outer East & NE", "projects_2024_25"] / a.loc["Outer East & NE", "lsoas"])
top = boroughs.nlargest(1, "dep_pct_london").iloc[0]
headlines = {
    "primary": {
        "text": "Inner West London gets 62% of London's FDI projects but holds only 11% of its most deprived neighbourhoods",
        "values": {"inner_west_fdi_share_pct": a.loc["Inner West", "fdi_share_2024_25"],
                   "inner_west_deprivation_share_pct": a.loc["Inner West", "deprivation_share"]}},
    "secondary": {
        "text": f"Inner West gets about {per_head:.0f}x more FDI projects per head than Outer East & North East",
        "values": {"per_head_ratio": round(per_head, 1)}},
    "supporting": [
        f"Inner East holds {a.loc['Inner East', 'deprivation_share']}% of London's most deprived neighbourhoods "
        f"but gets {a.loc['Inner East', 'fdi_share_2024_25']}% of FDI projects",
        f"Inner West's share of London FDI projects: "
        + ", ".join(f"{r.inner_west_share:.0f}% ({r.year})" for r in trend.itertuples()),
        f"Most deprived borough: {top.lad24nm} ({top.dep_pct_london}% of neighbourhoods in London's most deprived 20%)",
    ],
    "charts_for_web_app": [
        "Grouped bar: per sub-area, fdi_share_2024_25 (blue) vs deprivation_share (red). Data: section1_areas.csv",
        "Choropleth: boroughs shaded by dep_pct_london; tooltip adds area_fdi_share_2024_25. Data: section1_boroughs.csv",
        "Line: inner_west_share vs inner_east_share by year. Data: section1_trend.csv",
    ],
}
(OUT / "headlines.json").write_text(json.dumps(headlines, indent=2))

(OUT / "SOURCES.md").write_text("""# Section 1 sources

| Dataset | Publisher | Used for | Link |
|---|---|---|---|
| Inward Investment Results 2025 to 2026 (Tables 4.1, 4.12) | Department for Business and Trade | FDI projects and new jobs by London sub-area, 2023-24 to 2025-26 | GOV.UK (file: dbt-inward-investment-results-tables-2025-to-2026.ods) |
| English Indices of Deprivation 2025, File 1 (LSOA) | Ministry of Housing, Communities and Local Government | Neighbourhood deprivation ranks, rolled up to boroughs | https://www.gov.uk/government/statistics/announcements/english-indices-of-deprivation-2025 |
| English Indices of Deprivation 2025, Local Authority District Summaries | MHCLG | Borough ranks overall and by domain | same as above |
| Local Authority District boundaries | Office for National Statistics, via github.com/martinjc/UK-GeoJSON | Map shapes | https://github.com/martinjc/UK-GeoJSON |

All under the Open Government Licence v3.0. Boundaries: contains National Statistics and OS data © Crown copyright and database right.

Notes for the methods section:
- FDI is published only for London's five ITL2 sub-areas (TLI3-TLI7), so borough rows carry their sub-area's FDI (columns prefixed `area_`).
- "London's most deprived 20%" = the 998 most deprived of London's 4,994 LSOAs (London-relative ranking of IMD 2025).
- DBT suppressed values ([c]) are left blank, never zero. 2024-25 is the only year all five sub-areas are published.
- Association, not causation.
""")

print(f"Exported {len(boroughs)} boroughs (key: lad24cd), {len(areas)} sub-areas (key: itl2_cd) to export/")
