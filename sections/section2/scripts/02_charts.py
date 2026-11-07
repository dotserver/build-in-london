"""Step 2: draw the Section 2 charts from the cleaned tables.

Reads  clean/areas.csv, clean/boroughs.csv
Writes output/section2_main_chart.png, output/section2_homes_per_arrival.png, output/section2_boroughs_scatter.png

Run from the Section2_Pipeline folder:  python3 scripts/02_charts.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN, OUT = ROOT / "clean", ROOT / "output"
OUT.mkdir(exist_ok=True)
BLUE, ORANGE, GREEN, GREY = "#2a6fdb", "#d9822b", "#2f9e6e", "#555555"
SOURCE = ("Sources: DBT Inward Investment 2025-26 (via Section 1); ONS Census 2021 MIG001 (address one year before census); "
          "London planning applications 2021-25 (new-home schemes identified from descriptions).")

areas = pd.read_csv(CLEAN / "areas.csv").sort_values("fdi_share_2024_25", ascending=False)
boroughs = pd.read_csv(CLEAN / "boroughs.csv")


def tidy(ax):
    ax.spines[["top", "right"]].set_visible(False)


# 1. Main: where FDI goes, where newcomers arrive, where new homes get approved
fig, ax = plt.subplots(figsize=(10.5, 6.2), dpi=200)
x = range(len(areas))
series = [("fdi_share_2024_25", BLUE, "Share of London FDI projects (2024-25)"),
          ("share_of_london_arrivals_from_abroad", ORANGE, "Share of London's arrivals from abroad (Census 2021)"),
          ("share_of_london_new_home_approvals", GREEN, "Share of London's approved new-home schemes (2021-25)")]
w = 0.27
for i, (col, colour, label) in enumerate(series):
    bars = ax.bar([j + (i - 1) * w for j in x], areas[col], w, color=colour, label=label)
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.8, f"{b.get_height():.0f}%", ha="center", fontsize=8.5)
ax.set_xticks(list(x), areas["itl2_name"])
ax.set_ylabel("% of London total")
ax.set_ylim(0, 70)
tidy(ax)
ax.set_title("Investment and newcomers concentrate in the centre; new homes get approved further out", loc="left", fontsize=11.5)
ax.legend(frameon=False, fontsize=8.5)
inner = areas[areas["itl2_name"].str.startswith("Inner")]
fig.text(0.02, 0.075, f"Inner London takes {inner['fdi_share_2024_25'].sum():.0f}% of FDI projects and "
                      f"{inner['share_of_london_arrivals_from_abroad'].sum():.0f}% of arrivals from abroad, "
                      f"but only {inner['share_of_london_new_home_approvals'].sum():.0f}% of approved new-home schemes.",
         fontsize=9.5, weight="bold")
fig.text(0.02, 0.02, SOURCE, fontsize=6.5, color=GREY)
plt.tight_layout(rect=(0, 0.1, 1, 1))
plt.savefig(OUT / "section2_main_chart.png")

# 2. Homes keeping pace: approved new-home schemes per 1,000 new arrivals
a = areas.sort_values("new_homes_approved_per_1000_arrivals")
fig, ax = plt.subplots(figsize=(8.5, 4.4), dpi=200)
bars = ax.barh(a["itl2_name"], a["new_homes_approved_per_1000_arrivals"],
               color=[BLUE if n.startswith("Inner") else GREEN for n in a["itl2_name"]])
for b in bars:
    ax.text(b.get_width() + 0.4, b.get_y() + b.get_height() / 2, f"{b.get_width():.1f}", va="center", fontsize=9)
ax.set_xlabel("Approved new-home schemes per 1,000 people arriving from outside London")
tidy(ax)
ax.set_title("Where FDI concentrates, housing approvals lag furthest behind arrivals", loc="left", fontsize=11)
fig.text(0.01, 0.01, "Blue = Inner London (86% of FDI projects). Counts schemes, not individual homes.", fontsize=7, color=GREY)
plt.tight_layout(rect=(0, 0.04, 1, 1))
plt.savefig(OUT / "section2_homes_per_arrival.png")

# 3. Boroughs: arrivals from abroad vs housing approvals per arrival, coloured by sub-area FDI share
fig, ax = plt.subplots(figsize=(9, 6), dpi=200)
sc = ax.scatter(boroughs["arrived_from_abroad_per_1000"], boroughs["new_homes_approved_per_1000_arrivals"],
                c=boroughs["area_fdi_share_2024_25"], cmap="Blues", vmin=0, vmax=65, s=70, edgecolor="#333", linewidth=0.5)
label = set(boroughs.nlargest(6, "arrived_from_abroad_per_1000")["lad24nm"]) | \
        set(boroughs.nlargest(3, "new_homes_approved_per_1000_arrivals")["lad24nm"])
right_edge = boroughs["arrived_from_abroad_per_1000"].max() * 0.85
for _, r in boroughs[boroughs["lad24nm"].isin(label)].iterrows():
    left = r["arrived_from_abroad_per_1000"] > right_edge  # keep labels near the right edge inside the plot
    ax.annotate(r["lad24nm"], (r["arrived_from_abroad_per_1000"], r["new_homes_approved_per_1000_arrivals"]),
                textcoords="offset points", xytext=(-6 if left else 6, 6), ha="right" if left else "left", fontsize=8)
ax.set_xlabel("Arrivals from abroad per 1,000 residents (Census 2021)")
ax.set_ylabel("Approved new-home schemes per 1,000 new arrivals")
tidy(ax)
fig.colorbar(sc, ax=ax, shrink=0.7, label="Sub-area share of London FDI projects (%)")
ax.set_title("Boroughs taking the most newcomers approve the fewest new-home schemes per arrival", loc="left", fontsize=11)
plt.tight_layout()
plt.savefig(OUT / "section2_boroughs_scatter.png")

print("Saved 3 charts to output/")
