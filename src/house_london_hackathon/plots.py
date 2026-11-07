"""Static figures for slides (PNG). Palette: validated reference categorical slots 1-4."""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from house_london_hackathon.classify import GROUP_LABELS, classify, msoa_geometries
from house_london_hackathon.data import ROOT, load_borough_boundaries

OUT = ROOT / "outputs"
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
GROUP_COLORS = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a", "D": "#eda100"}

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "text.color": INK,
        "axes.labelcolor": INK2,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.edgecolor": "#c3c2b7",
        "font.size": 11,
    }
)


def _legend(ax, counts, loc):
    handles = [
        Patch(facecolor=GROUP_COLORS[g], edgecolor="none", label=f"{lab}  ({counts.get(g, 0)} MSOAs)")
        for g, lab in GROUP_LABELS.items()
    ]
    ax.legend(handles=handles, loc=loc, frameon=False, fontsize=10, labelcolor=INK)


def london_map(demand: str = "auto"):
    m = classify("london", demand)
    geo = msoa_geometries().merge(m[["msoa21cd", "group"]], on="msoa21cd").to_crs(27700)
    boroughs = load_borough_boundaries().to_crs(27700)

    fig, ax = plt.subplots(figsize=(11, 9))
    geo.plot(ax=ax, color=geo["group"].map(GROUP_COLORS), edgecolor=SURFACE, linewidth=0.3)
    boroughs.boundary.plot(ax=ax, color=INK, linewidth=0.6)
    ax.set_axis_off()
    ax.set_title(
        "London neighbourhoods (MSOAs) by housing pressure and deprivation",
        loc="left", fontsize=15, color=INK, pad=12,
    )
    ax.text(
        0, 1.0, f"Demand axis: {m.attrs['demand_label']}. Median split within London.",
        transform=ax.transAxes, color=INK2, fontsize=10,
    )
    _legend(ax, m["group"].value_counts().to_dict(), "lower left")
    fig.text(0.01, 0.01, "Sources: MHCLG English Indices of Deprivation 2025; ONS boundaries.",
             color=MUTED, fontsize=8)
    path = OUT / f"map_groups_london_{m.attrs['demand']}.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def scatter(scope: str = "london", demand: str = "auto"):
    m = classify(scope, demand)
    fig, ax = plt.subplots(figsize=(9, 7))
    for g in GROUP_LABELS:
        d = m[m["group"] == g]
        ax.scatter(d["deprivation_index"], d["demand_index"], s=14, color=GROUP_COLORS[g],
                   edgecolor=SURFACE, linewidth=0.5, alpha=0.9)
    ax.axvline(m["deprivation_index"].median(), color=MUTED, lw=1, ls="--")
    ax.axhline(m["demand_index"].median(), color=MUTED, lw=1, ls="--")
    ax.grid(color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.set_xlabel("People-deprivation index (z, higher = more deprived)")
    ax.set_ylabel(f"Demand index (z)\n{m.attrs['demand_label']}")
    r = m[["deprivation_index", "demand_index"]].corr().iloc[0, 1]
    ax.set_title(f"{scope.title()} MSOAs: the two axes correlate (r = {r:.2f})",
                 loc="left", fontsize=14, color=INK)
    _legend(ax, m["group"].value_counts().to_dict(), "lower right")
    path = OUT / f"scatter_groups_{scope}_{m.attrs['demand']}.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


if __name__ == "__main__":
    print(london_map())
    print(scatter("london"))
    print(scatter("england"))
