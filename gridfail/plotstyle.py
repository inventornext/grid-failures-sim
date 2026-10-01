"""Shared matplotlib style for all notebooks (colorblind-validated categorical order)."""
import matplotlib as mpl

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]
CRITICAL = "#d03b3b"   # protection thresholds / blackout markers (always labelled)
MUTED = "#8a8985"
TEXT = "#0b0b0b"
TEXT2 = "#52514e"


def apply():
    mpl.rcParams.update({
        "figure.figsize": (9, 4.6),
        "figure.dpi": 110,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
        "figure.facecolor": "#fcfcfb",
        "axes.facecolor": "#fcfcfb",
        "axes.prop_cycle": mpl.cycler(color=SERIES),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": TEXT2,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlecolor": TEXT,
        "axes.grid": True,
        "grid.color": "#e6e5e1",
        "grid.linewidth": 0.8,
        "xtick.color": TEXT2,
        "ytick.color": TEXT2,
        "lines.linewidth": 2.0,
        "legend.frameon": False,
        "font.size": 10,
    })


def threshold(ax, y, label, color=CRITICAL):
    ax.axhline(y, color=color, ls="--", lw=1.2)
    ax.annotate(label, xy=(1.0, y), xycoords=("axes fraction", "data"),
                xytext=(-4, 3), textcoords="offset points", ha="right", va="bottom",
                color=TEXT2, fontsize=9)
