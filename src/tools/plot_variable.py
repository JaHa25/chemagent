"""
Tool: plot_variable

Generates a matplotlib line plot of a process variable over a time window,
with vertical event markers overlaid. Saves to a temp PNG and returns the path.
The path can be rendered directly by Gradio as an Image component.
"""

import tempfile
import matplotlib
matplotlib.use("Agg")  # non-interactive backend, safe for server/agent use
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from smolagents import tool
from ..data.loader import load_timeseries, load_events
from ..data.query_utils import slice_window, validate_column

_EVENT_COLORS = {
    "process_change": "#e07b00",
    "disturbance":    "#cc2222",
    "sensor_fault":   "#7b22cc",
}
_EVENT_LABELS = {
    "feed_adjustment":  "Feed adjustment",
    "oxygen_limitation": "O2 limitation",
    "ph_sensor_drift":  "pH sensor drift",
}
_UNITS = {
    "temperature_c":    "degC",
    "ph":               "pH",
    "do_percent":       "% saturation",
    "biomass_gL":       "g/L",
    "substrate_gL":     "g/L",
    "product_titer_gL": "g/L",
    "feed_rate_Lh":     "L/h",
}


@tool
def plot_variable(column: str, t_start: float, t_end: float) -> str:
    """Plot a bioreactor process variable over a time window with event markers.

    Saves the figure to a temporary PNG file and returns its file path,
    which Gradio can render as an image.

    Args:
        column: Process variable to plot. One of: temperature_c, ph,
            do_percent, biomass_gL, substrate_gL, product_titer_gL, feed_rate_Lh.
        t_start: Start of the time window in process hours (inclusive).
        t_end: End of the time window in process hours (exclusive).

    Returns:
        Absolute path to the saved PNG file.
    """
    validate_column(column)
    df = load_timeseries()
    window = slice_window(df, t_start, t_end)
    events = load_events()

    fig, ax = plt.subplots(figsize=(10, 4))

    ax.plot(window["t_hours"], window[column], lw=0.8, color="#1f77b4", alpha=0.9)

    # Overlay event markers that fall within the window
    legend_handles = []
    seen_labels = set()
    for _, ev in events.iterrows():
        ev_t = ev["event_time_h"]
        if t_start <= ev_t <= t_end:
            color = _EVENT_COLORS.get(ev["event_type"], "grey")
            label = _EVENT_LABELS.get(ev["event_name"], ev["event_name"])
            line = ax.axvline(ev_t, color=color, lw=1.4, ls="--", alpha=0.8,
                              label=label if label not in seen_labels else "_nolegend_")
            if label not in seen_labels:
                legend_handles.append(line)
                seen_labels.add(label)

    unit = _UNITS.get(column, "")
    ax.set_xlabel("Process time (h)", fontsize=10)
    ax.set_ylabel(f"{column} ({unit})", fontsize=10)
    ax.set_title(f"{column}: t=[{t_start}, {t_end}) h", fontsize=11)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(6))
    ax.grid(True, lw=0.3, alpha=0.5)
    if legend_handles:
        ax.legend(fontsize=8, loc="best")

    fig.tight_layout()

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fig.savefig(tmp.name, dpi=130, bbox_inches="tight")
    plt.close(fig)

    return tmp.name
