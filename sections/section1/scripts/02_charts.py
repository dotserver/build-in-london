"""Step 2: draw the Section 1 charts from the cleaned tables.

Reads  clean/areas.csv, clean/london_trend.csv
Writes output/section1_main_chart.png, output/section1_trend_chart.png

Run from the Section1_Pipeline folder:  python3 scripts/02_charts.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN, OUT = ROOT / "clean", ROOT / "output"
OUT.mkdir(exist_ok=True)
BLUE, RED = "#2a6fdb", "#e0553d"

areas = pd.read_csv(CLEAN / "areas.csv").sort_values("fdi_share_2024-25", ascending=False)
trend = pd.read_csv(CLEAN / "london_trend.csv")

# Main chart: FDI share vs deprivation share, side by side per sub-area
fig, ax = plt.subplots(figsize=(10, 6.4), dpi=200)
x = range(len(areas))
bars = [ax.bar([i - 0.19 for i in x], areas["fdi_share_2024-25"], 0.38, color=BLUE,
               label="Share of London FDI projects (DBT, 2024-25)"),
        ax.bar([i + 0.19 for i in x], areas["deprivation_share"], 0.38, color=RED,
               label="Share of London's most deprived neighbourhoods (IMD 2025)")]
for group in bars:
    for b in group:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.8, f"{b.get_height():.0f}%", ha="center", fontsize=9)
ax.set_xticks(list(x), areas["area"])
ax.set_ylabel("% of London total")
ax.set_ylim(0, 70)
ax.spines[["top", "right"]].set_visible(False)
ax.set_title("Where overseas investment goes vs where deprivation sits", loc="left")
ax.legend(frameon=False, fontsize=8.5)

a = areas.set_index("area")
per100 = a["projects_2024-25"] / a["lsoas"] * 100  # unrounded, so the ratio is exact
ratio = per100["Inner West"] / per100["Outer East & NE"]
fig.text(0.02, 0.07, f"Per head: Inner West gets {per100['Inner West']:.0f} FDI projects per 100 neighbourhoods; "
                     f"Outer East & NE gets {per100['Outer East & NE']:.1f} (about {ratio:.0f}x less).", fontsize=9.5, weight="bold")
fig.text(0.02, 0.02, "Sources: DBT Inward Investment Results 2025-26 (Table 4.12); MHCLG English Indices of Deprivation 2025.",
         fontsize=7, color="#555")
plt.tight_layout(rect=(0, 0.1, 1, 1))
plt.savefig(OUT / "section1_main_chart.png")

# Trend chart: is the gap persistent?
fig, ax = plt.subplots(figsize=(8, 4.5), dpi=200)
for col, colour, label in [("inner_west_share", BLUE, "Inner West"), ("inner_east_share", RED, "Inner East (most deprived)")]:
    ax.plot(trend["year"], trend[col], "-o", color=colour, lw=2.5, label=label)
    for y, v in zip(trend["year"], trend[col]):
        ax.annotate(f"{v:.0f}%", (y, v), textcoords="offset points", xytext=(0, 9), ha="center", color=colour, weight="bold")
ax.set_ylim(0, 80)
ax.set_ylabel("Share of London FDI projects (%)")
ax.spines[["top", "right"]].set_visible(False)
ax.set_title("Inner West keeps about two-thirds of London FDI every year", loc="left", fontsize=11)
ax.legend(frameon=False)
plt.tight_layout()
plt.savefig(OUT / "section1_trend_chart.png")

print(f"Saved charts to output/  (per-head ratio: {ratio:.1f}x)")
