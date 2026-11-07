# Section 2 sources

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
