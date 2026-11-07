# House London! #3 — Data Hackathon

London housing crisis: planning & housing data sprint (Newspeak House, 7 Nov 2026).

## Question
_TODO: one sentence — the decision this analysis informs._

## Setup
```bash
brew install uv        # once
uv sync                # creates .venv with all dependencies
code .                 # open in VS Code; pick the .venv kernel for notebooks
```

## Run
- Notebooks: `notebooks/` (kernel: `.venv`)
- Dashboard: `uv run streamlit run app/streamlit_app.py`
- Add a package: `uv add <name>`

## Web app (deployed site)
- Static site in `web/` (Vercel serves it via `vercel.json`; no build step, no backend).
- Refresh data: `uv run python scripts/export_web.py` -> `web/data/*.json|geojson`.
- Preview locally: `cd web && python3 -m http.server 8765` -> http://localhost:8765
- Teammate pipelines live in `sections/sectionN/` (Section 1: `cd sections/section1 && sh run_all.sh`,
  or run its scripts with `uv run --project ../.. python scripts/0X_*.py`); `export_web.py` reads their `export/` folder.
- Adding a section: add `export_sectionN()` to `scripts/export_web.py`, put the
  markup in the `#sN` block of `web/index.html`, and the code in `web/js/sectionN.js`
  (shared helpers — colours, tooltip, number formats — are in `web/js/common.js`).
  Join data on ONS codes (`lad24cd`, `msoa21cd`), never names.

## Layout
- `data/raw/` downloads (git-ignored) · `data/processed/` cleaned outputs
- `src/house_london_hackathon/` shared loaders/cleaning
- `outputs/` charts and the brief

## Data sources
| Dataset | Publisher | URL | Notes |
|---|---|---|---|
| Borough boundaries (LAD Dec 2024) | ONS Open Geography | geoportal.statistics.gov.uk | E09 codes |
| DBT Inward Investment Results 2025-26 (Tables 4.1, 4.12) — Section 1 | Department for Business and Trade | GOV.UK | FDI projects/jobs by London ITL2 sub-area; see `sections/section1/export/SOURCES.md` |
| ONS Census 2021 MIG001; London planning applications 2021-25 — Section 2 | ONS; council portals | see `sections/section2/export/SOURCES.md` | arrivals vs approved new-home schemes |
| English Indices of Deprivation 2025 (File 7) | MHCLG | gov.uk/government/statistics/english-indices-of-deprivation-2025 | LSOA 2021, England; LAD 2024 codes included |
| OA/LSOA/MSOA lookup (Dec 2021) | ONS Open Geography | OA_LSOA_MSOA_EW_DEC_2021_LU_v3 | LSOA -> MSOA |
| LSOA boundaries (Dec 2021, BGC V5) | ONS Open Geography | Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V5 | for brownfield spatial join |
| Brownfield land registers | MHCLG planning.data.gov.uk | files.planning.data.gov.uk/dataset/brownfield-land.csv | active sites only (no end-date) |
| ~~WhereToBuild~~ (not used) | University of Warwick | wheretobuild.warwick.ac.uk | Only copy available was corrupted by a spreadsheet export; demand axis uses IoD 2025 wider-barriers (unmet housing demand) instead |

Section 3 tables: `uv run python -m house_london_hackathon.section3` -> `data/processed/section3_{lsoa,msoa,lad}.{parquet,csv}`.

## Assumptions & caveats
- Demand axis (Section 3 groups, app): IoD 2025 wider-barriers sub-domain = unmet housing demand (overcrowding, homelessness, affordability); correlated with deprivation (r ≈ 0.7).
- Brownfield: sites > 100 ha treated as unit-entry errors (hectares nulled, flagged in `bf_sites_hectares_suspect`); ~32% of sites have no dwelling estimate (`bf_sites_missing_dwellings`), e.g. all of Tower Hamlets and Enfield -> dwelling totals are lower bounds.
- MSOA/LAD domain scores are population-weighted means of LSOA scores (not official LAD summary measures).
- IoD 2025 notes an ONS lookup error affecting some LSOA->LAD assignments; see the publication notes.
- 
