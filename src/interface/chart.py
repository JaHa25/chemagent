"""
Interactive Plotly chart builder for ChemAgent.

Builds a time-series figure with:
 - Configurable variable traces
 - Event marker bands
 - Optional highlighted analysis window
 - Time-range zooming
"""

from __future__ import annotations

import plotly.graph_objects as go

from ..data.loader import load_timeseries

# ---------------------------------------------------------------------------
# Variable config
# ---------------------------------------------------------------------------

VARIABLE_CONFIG: dict[str, dict] = {
    "ph":               {"label": "pH",         "color": "#6366f1", "unit": ""},
    "do_percent":       {"label": "DO (%)",      "color": "#06b6d4", "unit": "%"},
    "temperature_c":    {"label": "Temp (°C)",   "color": "#f59e0b", "unit": "°C"},
    "biomass_gL":       {"label": "Biomass",     "color": "#10b981", "unit": " g/L"},
    "substrate_gL":     {"label": "Substrate",   "color": "#f97316", "unit": " g/L"},
    "product_titer_gL": {"label": "Titer",       "color": "#ec4899", "unit": " g/L"},
    "feed_rate_Lh":     {"label": "Feed rate",   "color": "#8b5cf6", "unit": " L/h"},
}

VAR_LABEL_TO_COL: dict[str, str] = {
    v["label"].split(" ")[0]: k for k, v in VARIABLE_CONFIG.items()
}
# Explicit mapping for the CheckboxGroup labels
VAR_CHOICES = ["pH", "DO", "Temp", "Biomass", "Substrate", "Titer", "Feed"]
VAR_CHOICE_TO_COL = {
    "pH":       "ph",
    "DO":       "do_percent",
    "Temp":     "temperature_c",
    "Biomass":  "biomass_gL",
    "Substrate":"substrate_gL",
    "Titer":    "product_titer_gL",
    "Feed":     "feed_rate_Lh",
}

DEFAULT_VAR_CHOICES = ["pH", "DO", "Temp"]

# ---------------------------------------------------------------------------
# Known events
# ---------------------------------------------------------------------------

EVENTS = [
    {"label": "Feed adj.",  "t_start": 30, "t_end": 34,  "color": "#f59e0b"},
    {"label": "O2 limit",   "t_start": 38, "t_end": 42,  "color": "#06b6d4"},
    {"label": "pH drift",   "t_start": 42, "t_end": 72,  "color": "#6366f1"},
]


# ---------------------------------------------------------------------------
# Figure builder
# ---------------------------------------------------------------------------

def build_chart(
    var_choices: list[str] | None = None,
    highlight_t_start: float | None = None,
    highlight_t_end: float | None = None,
    x_range: tuple[float, float] = (0.0, 72.0),
    downsample: int = 3,
) -> go.Figure:
    """Return a Plotly figure for the bioreactor run.

    Args:
        var_choices: List of display labels (e.g. ["pH", "DO"]).
        highlight_t_start: Start of analysis window to highlight (h).
        highlight_t_end:   End of analysis window to highlight (h).
        x_range:           Visible x-axis range (t_start, t_end).
        downsample:        Take every Nth row for performance.
    """
    df = load_timeseries()
    if var_choices is None:
        var_choices = DEFAULT_VAR_CHOICES

    df_plot = df.iloc[::downsample].copy()
    columns = [VAR_CHOICE_TO_COL[v] for v in var_choices if v in VAR_CHOICE_TO_COL]
    if not columns:
        columns = ["ph"]

    fig = go.Figure()

    # --- variable traces ------------------------------------------------
    for col in columns:
        cfg = VARIABLE_CONFIG[col]
        fig.add_trace(go.Scatter(
            x=df_plot["t_hours"],
            y=df_plot[col],
            name=cfg["label"],
            line=dict(color=cfg["color"], width=2),
            hovertemplate=(
                f"<b>{cfg['label']}</b>: %{{y:.3f}}{cfg['unit']}"
                "<br>t = %{x:.2f} h<extra></extra>"
            ),
        ))

    # --- event bands ----------------------------------------------------
    for ev in EVENTS:
        fig.add_vrect(
            x0=ev["t_start"], x1=ev["t_end"],
            fillcolor=ev["color"], opacity=0.07, line_width=0,
            layer="below",
        )
        fig.add_vline(
            x=ev["t_start"],
            line=dict(color=ev["color"], width=1.5, dash="dot"),
            annotation=dict(
                text=ev["label"],
                font=dict(size=11, color=ev["color"]),
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor=ev["color"],
                borderwidth=1,
                borderpad=3,
            ),
            annotation_position="top left",
        )

    # --- analysis window highlight -------------------------------------
    if highlight_t_start is not None and highlight_t_end is not None:
        fig.add_vrect(
            x0=highlight_t_start, x1=highlight_t_end,
            fillcolor="#818cf8", opacity=0.18,
            line=dict(color="#6366f1", width=2, dash="dash"),
            layer="above",
            annotation=dict(
                text="Analysis window",
                font=dict(size=10, color="#6366f1", family="monospace"),
                bgcolor="rgba(255,255,255,0.9)",
            ),
            annotation_position="top right",
        )

    # --- layout ---------------------------------------------------------
    fig.update_layout(
        height=400,
        margin=dict(l=50, r=20, t=40, b=60),
        plot_bgcolor="#f8fafc",
        paper_bgcolor="white",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            y=-0.22,
            x=0,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#e5e7eb",
            borderwidth=1,
            font=dict(size=11),
        ),
        xaxis=dict(
            title="Process time (h)",
            gridcolor="#e5e7eb",
            range=list(x_range),
            dtick=12,
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            title="Value",
            gridcolor="#e5e7eb",
            tickfont=dict(size=11),
        ),
        font=dict(family="Inter, system-ui, sans-serif", size=12),
        dragmode="pan",
        modebar=dict(remove=["toImage", "sendDataToCloud"]),
    )

    return fig
