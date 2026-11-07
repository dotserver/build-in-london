# Section 1 sources

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
