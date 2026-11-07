# Section 2 pipeline: is housing keeping up where FDI and newcomers land? (London)

Question: in the areas where FDI concentrates (e.g. Canary Wharf), is new housing keeping pace with
migration, and what kind of housing is being approved?

```
raw/  ──01_clean.py──▶  clean/  ──02_charts.py────▶  output/*.png
                                ──03_build_map.py──▶  output/london_map.html
                                ──04_export.py─────▶  export/  (team format, keyed on lad24cd / itl2_cd)
```

## Run it

```
pip install -r requirements.txt
sh run_all.sh
```

`clean/`, `output/` and `export/` are already included. Open `output/london_map.html` in a browser:
hover a borough for the summary, click for the full profile, switch shading with the buttons.

## Folders

| Folder | Contents |
|---|---|
| `raw/` | Original datasets, untouched (planning file gzipped; pandas reads it directly) |
| `scripts/` | `01_clean.py`, `02_charts.py`, `03_build_map.py`, `04_export.py` |
| `clean/` | `boroughs.csv`, `areas.csv`, `yearly.csv`, `canary_wharf_wards.csv`, `map_data.json`, `cleaning_log.json` |
| `output/` | 3 charts + `london_map.html` |
| `export/` | Team hand-off: `section2_boroughs.csv` (key `lad24cd`), `section2_areas.csv` (key `itl2_cd`), `section2_yearly.csv`, `section2_canary_wharf_wards.csv`, `headlines.json`, `SOURCES.md` |
| `web/` | `map_template.html`: map design and code (same design as Section 1) |

## Raw data

| File | Source | What it is |
|---|---|---|
| `london_planning_applications_2015_2025.csv.gz` | London planning authority portals (friend's dataset: foundations_london_housing_2015_2025) | 243,926 housing-related planning applications with status, decision dates, ward, coordinates |
| `census2021_mig001_ltla_inflow.csv` (+ metadata) | ONS Census 2021, MIG001 | Where each borough's residents lived one year before the census |
| `section1_boroughs.csv`, `section1_areas.csv` | Section 1 export | FDI share by sub-area; borough-to-sub-area mapping |
| `lad_boundaries_ons.geojson` | ONS via github.com/martinjc/UK-GeoJSON | Borough shapes |

## Cleaning log (what 01_clean.py does, and why)

1. **Matched planning authorities to borough codes.** Fixed short names (Kensington, Kingston, Richmond, City) and
   placed the 564 applications from the two development corporations (Old Oak and Park Royal, London Legacy),
   which span several boroughs, using each application's coordinates.
2. **Kept 2021-2025.** Before 2021 only Barking and Dagenham has records (146 rows), so earlier years aren't comparable.
3. **Removed duplicates** on borough + application reference.
4. **Identified new-home schemes from the description text (9,089 applications).** The dataset's `app_type` and
   `app_size` labels are inconsistent between council portals (for example, condition discharges tagged "Full";
   Newham has 37 "Large" applications, Southwark 1,145). A scheme counts as new homes if it proposes new build,
   conversion or change of use creating dwellings, and isn't a follow-up (conditions, amendments, certificates)
   or a householder extension.
5. **Did not use `n_dwellings`.** It is filled for under 1 in 10 new-home schemes and repeats across follow-up
   applications (one 13,046-home scheme appears in two boroughs and in many amendments), so dwelling totals would mislead.
   Section 2 counts schemes, not homes.
6. **Defined outcomes.** Approved = Permitted or Conditions; refused = Rejected. Rates use decided applications only.
7. **Flagged housing types from the text:** affordable, tall building (10+ storeys), build to rent, student, co-living.
   These are mentions, not official tenure figures.
8. **Reshaped Census migration.** Summed over sex and age; split movers into arrived from abroad, from the rest of the UK,
   from another London borough, and within the borough. "New arrivals" = from abroad + rest of UK (new to London).
9. **Joined to Section 1** on `lad24cd` for the sub-area and its FDI share, then rolled boroughs up to sub-areas.
10. **Canary Wharf lens.** Tower Hamlets wards Canary Wharf, Blackwall and Cubitt Town, Island Gardens, Poplar and
    Limehouse are flagged as the Canary Wharf cluster.

`clean/cleaning_log.json` records the row counts at each step.

## Key results

| Sub-area | FDI projects | Arrivals from abroad | Approved new-home schemes | Schemes per 1,000 new arrivals |
|---|---|---|---|---|
| Inner West | 62.1% | 23.7% | 14.0% | 8.2 |
| Inner East | 23.5% | 32.1% | 14.8% | 6.1 |
| Outer West & NW | 7.5% | 22.9% | 23.7% | 14.6 |
| Outer East & NE | 3.8% | 12.4% | 26.0% | 25.4 |
| Outer South | 3.1% | 8.8% | 21.5% | 27.7 |

- Inner London takes 86% of FDI projects and 56% of arrivals from abroad, but only 29% of approved new-home schemes.
- Outer London approves about 3x more new-home schemes per new arrival than inner London.
- Inner West has the highest approval rate (80%), so the gap comes from fewer schemes coming forward, not more refusals.
- Canary Wharf cluster: 22 new-home applications 2021-25, 6 approved. Small numbers, so treat as indicative.

## Limits

- Counts schemes, not homes: one tower and one house conversion each count as one.
- Council portals record applications differently, so compare rates and shares more than raw counts.
  Tower Hamlets, for example, has far fewer records than outer boroughs.
- Migration is the year before Census 2021, during COVID-19 restrictions; planning covers 2021-25.
- "Quality" here is limited to what descriptions mention (affordable, tall, build to rent, student, co-living).
  Space standards or completions would need other data (e.g. the GLA Planning London Datahub).
- Association, not causation.
