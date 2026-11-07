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

## Layout
- `data/raw/` downloads (git-ignored) · `data/processed/` cleaned outputs
- `src/house_london_hackathon/` shared loaders/cleaning
- `outputs/` charts and the brief

## Data sources
| Dataset | Publisher | URL | Notes |
|---|---|---|---|
| Borough boundaries (LAD Dec 2024) | ONS Open Geography | geoportal.statistics.gov.uk | E09 codes |

## Assumptions & caveats
- 
