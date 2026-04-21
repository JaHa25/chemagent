"""
Tool: compute_trend

Fits a linear trend (slope + intercept) to a process variable
over a time window using least-squares regression.
"""

import numpy as np
from scipy import stats
from smolagents import tool
from ..data.loader import load_timeseries
from ..data.query_utils import slice_window, validate_column


@tool
def compute_trend(column: str, t_start: float, t_end: float) -> str:
    """Fit a linear trend to a process variable over a time window.

    Uses ordinary least-squares regression. Reports slope, intercept,
    R², p-value, and a plain-language direction summary.

    Args:
        column: Process variable to analyse. One of: temperature_c, ph,
            do_percent, biomass_gL, substrate_gL, product_titer_gL, feed_rate_Lh.
        t_start: Start of the time window in process hours (inclusive).
        t_end: End of the time window in process hours (exclusive).

    Returns:
        A plain-text report with slope (units/h), intercept, R², p-value,
        and a direction label (increasing / decreasing / flat).
    """
    validate_column(column)
    df = load_timeseries()
    window = slice_window(df, t_start, t_end)

    t = window["t_hours"].to_numpy()
    y = window[column].to_numpy()

    result = stats.linregress(t, y)
    slope = result.slope
    intercept = result.intercept
    r2 = result.rvalue ** 2
    pvalue = result.pvalue

    if pvalue > 0.05 or abs(slope) < 1e-6:
        direction = "flat (no statistically significant trend)"
    elif slope > 0:
        direction = "increasing"
    else:
        direction = "decreasing"

    unit_map = {
        "temperature_c": "degC/h", "ph": "pH/h", "do_percent": "%/h",
        "biomass_gL": "g/L/h", "substrate_gL": "g/L/h",
        "product_titer_gL": "g/L/h", "feed_rate_Lh": "(L/h)/h",
    }
    unit = unit_map.get(column, "/h")

    return (
        f"Linear trend for '{column}' over t=[{t_start}, {t_end}) h:\n"
        f"  slope     = {slope:.5f} {unit}\n"
        f"  intercept = {intercept:.4f}\n"
        f"  R^2       = {r2:.4f}\n"
        f"  p-value   = {pvalue:.2e}\n"
        f"  direction : {direction}"
    )
