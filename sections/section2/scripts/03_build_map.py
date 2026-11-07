"""Step 3: build the interactive map as one self-contained HTML file.

Reads  clean/map_data.json, web/map_template.html
Writes output/london_map.html  (double-click to open: hover = summary, click = full profile)

Run from the Section2_Pipeline folder:  python3 scripts/03_build_map.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
(ROOT / "output").mkdir(exist_ok=True)

template = (ROOT / "web" / "map_template.html").read_text()
data = (ROOT / "clean" / "map_data.json").read_text()

page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        + template.replace("__DATA__", data) + "</html>")
(ROOT / "output" / "london_map.html").write_text(page)
print("Saved output/london_map.html")
