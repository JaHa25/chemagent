"""
Tool: summary_statistics

Returns mean, min, max, std, and count for one process variable
over a given time window.
"""

from smolagents import tool
from ..data.loader import load_timeseries, T_MAX
from ..data.query_utils import slice_window, validate_column


@tool
def summary_statistics(column: str, t_start: float, t_end: float) -> str:
    """Compute descriptive statistics for a bioreactor variable over a time window.

    Args:
        column: Process variable to analyse. One of: temperature_c, ph,
            do_percent, biomass_gL, substrate_gL, product_titer_gL, feed_rate_Lh.
        t_start: Start of the time window in process hours (inclusive).
        t_end: End of the time window in process hours (exclusive).
            Use t_end=72.0 for the end of the run. For "last 12 hours" use
            t_start=60.0, t_end=72.0.

    Returns:
        A plain-text summary with mean, min, max, std, and sample count.
    """
    validate_column(column)
    df = load_timeseries()
    window = slice_window(df, t_start, t_end)
    s = window[column]

    return (
        f"Statistics for '{column}' over t=[{t_start}, {t_end}) h "
        f"({len(s)} samples):\n"
        f"  mean = {s.mean():.4f}\n"
        f"  min  = {s.min():.4f}\n"
        f"  max  = {s.max():.4f}\n"
        f"  std  = {s.std():.4f}"
    )
