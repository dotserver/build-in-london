# Section 1 pipeline: where investment and deprivation sit (London)

Raw data in, cleaned tables out, then charts and an interactive map. Every number in Section 1
can be rebuilt from the original downloads by running three scripts.

```
raw/  ──01_clean.py──▶  clean/  ──02_charts.py────▶  output/*.png
                                ──03_build_map.py──▶  output/london_map.html
                                ──04_export.py─────▶  export/  (team format, keyed on lad24cd / itl2_cd)
```

## Run it

```
pip install -r requirements.txt
sh run_all.sh            # or run the three scripts in scripts/ one by one
```

`clean/` and `output/` are already included, so results can be viewed without running anything.
Open `output/london_map.html` in a browser: hover a borough for the summary, click for the full profile.

## Folders

| Folder | Contents |
|---|---|
| `raw/` | Original datasets, untouched |
| `scripts/` | `01_clean.py` (cleaning), `02_charts.py` (static charts), `03_build_map.py` (interactive map), `04_export.py` (team format) |
| `clean/` | Tidy outputs of step 1: `boroughs.csv`, `areas.csv`, `london_trend.csv`, `map_data.json` |
| `output/` | Final charts and `london_map.html` |
| `export/` | Team hand-off: `section1_boroughs.csv` (key `lad24cd`), `section1_areas.csv` (key `itl2_cd`), `section1_trend.csv`, `headlines.json`, `SOURCES.md` |
| `web/` | `map_template.html`: map design and code; step 3 inserts the data into it |

## Raw data

| File | Source | What it is |
|---|---|---|
| `dbt-inward-investment-results-tables-2025-to-2026.ods` | Department for Business and Trade | FDI projects and jobs by UK region and ITL2 area, 2023-24 to 2025-26 |
| `imd2025_lsoa.csv` | MHCLG, English Indices of Deprivation 2025 (File 1) | Deprivation rank and decile for all 33,755 neighbourhoods (LSOAs) in England |
| `imd2025_local_authority_summaries.csv` | MHCLG, IoD 2025 | Deprivation ranks for all 296 English councils, overall and by domain |
| `lad_boundaries_ons.geojson` | ONS boundaries via github.com/martinjc/UK-GeoJSON | Council boundary shapes (London boroughs unchanged since 1965) |

## Cleaning log (what 01_clean.py does, and why)

1. **Filtered to London.** Kept the 4,994 neighbourhoods whose council code starts `E09` (the 33 London boroughs).
2. **London-vs-London yardstick.** Re-ranked those neighbourhoods against each other and flagged the most deprived
   20% (998). Section 1 compares boroughs within London, so this is fairer than England-wide deciles.
   The England figure (deciles 1-2) is kept alongside for context.
3. **Rolled up to boroughs.** Counted neighbourhoods and flagged ones per borough; converted to % of each borough.
4. **Added borough ranks.** Joined the council summary file; kept England ranks (1-296) and derived London ranks (1-33)
   for overall deprivation and each domain (income, employment, education, health, crime, housing, environment,
   child and older-people poverty).
5. **Grouped boroughs into 5 sub-areas.** DBT publishes FDI only for London's five ITL2 areas, not boroughs,
   so boroughs were assigned to their ITL2 area (2021 boundaries). Checked all 33 map to one.
6. **Extracted FDI from the spreadsheet.** Pulled the five London rows from Table 4.12 (projects and new jobs, three
   years) and London's totals from Table 4.1.
7. **Handled suppressed values.** DBT marks confidential cells `[c]` and missing ones `-`. These became blanks,
   never zeros, so they can't distort totals.
8. **Chose 2024-25 for shares.** It is the only year all five areas are published. The trend uses London's
   Table 4.1 total as the denominator, so suppressed areas don't skew it.
9. **Calculated the comparison measures.** Each area's share of London's FDI projects and jobs, share of London's
   most deprived neighbourhoods, and projects per 100 neighbourhoods (neighbourhoods hold ~1,500 people each,
   so this approximates a per-head rate).
10. **Prepared map shapes.** Converted borough boundaries from longitude/latitude to flat SVG paths, dropping points
    under ~1px apart to keep the file small. Checked boundaries and data cover the same 33 boroughs.

## Key results

| Sub-area | Share of London FDI projects | Share of London's most deprived areas | Projects per 100 neighbourhoods |
|---|---|---|---|
| Inner West | 62.1% | 10.7% | 39.9 |
| Inner East | 23.5% | 42.1% | 7.7 |
| Outer West & NW | 7.5% | 18.3% | 2.7 |
| Outer East & NE | 3.8% | 21.3% | 1.5 |
| Outer South | 3.1% | 7.5% | 1.7 |

Inner West gets about 27x more projects per head than Outer East & NE, and has held 62-66% of London's FDI
projects in each of the last three years.

## Limits

- FDI exists only at sub-area level, so borough figures on the map show the sub-area's investment.
- Counts single-site projects; multi-site UK projects can't be placed in an area.
- Shows where investment and deprivation sit, not that one causes the other.

Licences: DBT and MHCLG data under the Open Government Licence v3.0. Boundaries: Contains National Statistics
and OS data © Crown copyright and database right.
