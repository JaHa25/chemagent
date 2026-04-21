"""Quick visual check of the synthetic bioreactor dataset."""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ts = pd.read_csv(DATA_DIR / "bioreactor_timeseries.csv")
events = pd.read_csv(DATA_DIR / "events.csv")

t = ts["t_hours"]
EVENT_COLORS = {"process_change": "#e07b00", "disturbance": "#cc2222", "sensor_fault": "#7b22cc"}
EVENT_LABELS = {
    "feed_adjustment": "Feed adjustment",
    "oxygen_limitation": "O\u2082 limitation",
    "ph_sensor_drift": "pH sensor drift",
}

def add_event_lines(ax):
    for _, ev in events.iterrows():
        color = EVENT_COLORS.get(ev["event_type"], "grey")
        ax.axvline(ev["event_time_h"], color=color, lw=1.2, ls="--", alpha=0.7,
                   label=EVENT_LABELS.get(ev["event_name"], ev["event_name"]))

fig, axes = plt.subplots(4, 2, figsize=(14, 16), sharex=True)
fig.suptitle("Synthetic Bioreactor Dataset: 72 h, 1-min resolution", fontsize=13, fontweight="bold")

panels = [
    ("temperature_c", "Temperature (°C)", "#d62728"),
    ("ph",            "pH",               "#1f77b4"),
    ("do_percent",    "Dissolved O\u2082 (% sat)", "#2ca02c"),
    ("biomass_gL",    "Biomass (g/L)",    "#8c564b"),
    ("substrate_gL",  "Substrate (g/L)",  "#ff7f0e"),
    ("product_titer_gL", "Product titer (g/L)", "#9467bd"),
    ("feed_rate_Lh",  "Feed rate (L/h)",  "#17becf"),
]

for ax, (col, ylabel, color) in zip(axes.flat, panels):
    ax.plot(t, ts[col], color=color, lw=0.6, alpha=0.85)
    add_event_lines(ax)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(12))
    ax.grid(True, lw=0.3, alpha=0.5)

# Hide the unused 8th subplot
axes.flat[-1].set_visible(False)

# Add event legend to last visible axis
handles, labels = axes.flat[5].get_legend_handles_labels()
axes.flat[5].legend(handles[1:], labels[1:], fontsize=7, loc="lower right")

for ax in axes[-1]:
    ax.set_xlabel("Time (h)", fontsize=9)

fig.tight_layout()
out = DATA_DIR / "dataset_overview.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
print(f"Saved -> {out}")
plt.show()
