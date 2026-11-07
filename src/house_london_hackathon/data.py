"""Data loading helpers. Join datasets on ONS codes (e.g. E09000001), never on names."""

from pathlib import Path

import geopandas as gpd
import requests

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"

# ONS Open Geography: Local Authority Districts (Dec 2024), generalised boundaries.
# E09* codes are the 32 London boroughs plus the City of London.
BOROUGHS_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Local_Authority_Districts_December_2024_Boundaries_UK_BGC/FeatureServer/0/query"
    "?where=LAD24CD%20LIKE%20%27E09%25%27&outFields=LAD24CD,LAD24NM&outSR=4326&f=geojson"
)


def download(url: str, filename: str, force: bool = False) -> Path:
    """Download url into data/raw/filename once; reuse the cached copy afterwards."""
    path = DATA_RAW / filename
    if path.exists() and not force:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return path


def load_borough_boundaries() -> gpd.GeoDataFrame:
    """London borough polygons (WGS84) with columns: code, name, geometry."""
    path = download(BOROUGHS_URL, "london_boroughs.geojson")
    gdf = gpd.read_file(path)
    return gdf.rename(columns={"LAD24CD": "code", "LAD24NM": "name"})[
        ["code", "name", "geometry"]
    ]
