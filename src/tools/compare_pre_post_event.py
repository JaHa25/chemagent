"""
Tool: compare_pre_post_event

Compares a process variable in a window immediately before vs. immediately
after a named operational event.
"""

import numpy as np
from scipy import stats
from smolagents import tool
from ..data.loader import load_timeseries
from ..data.query_utils import slice_window, validate_column
from ..data.event_lookup import get_event_window


@tool
def compare_pre_post_event(
    event_name: str,
    column: str,
    window_h: float = 6.0,
) -> str:
    """Compare a process variable before and after a named bioreactor event.

    Slices [event_start - window_h, event_start) as the pre-event window and
    [event_end, event_end + window_h) as the post-event window, then reports
    mean, slope, and percent change, plus a Welch t-test for significance.

    Args:
        event_name: Name of the event. One of: feed_adjustment,
            oxygen_limitation, ph_sensor_drift.
        column: Process variable to compare. One of: temperature_c, ph,
            do_percent, biomass_gL, substrate_gL, product_titer_gL, feed_rate_Lh.
        window_h: Hours before event_start and after event_end to use as
            comparison windows (default 6.0 h).

    Returns:
        A plain-text report with pre/post means, slopes, percent change,
        absolute change, and t-test result.
    """
    validate_column(column)
    ev_start, ev_end = get_event_window(event_name)
    df = load_timeseries()

    pre  = slice_window(df, ev_start - window_h, ev_start)
    post = slice_window(df, ev_end, ev_end + window_h)

    pre_vals  = pre[column].to_numpy()
    post_vals = post[column].to_numpy()
    pre_t     = pre["t_hours"].to_numpy()
    post_t    = post["t_hours"].to_numpy()

    pre_mean  = float(pre_vals.mean())
    post_mean = float(post_vals.mean())
    abs_change = post_mean - pre_mean
    pct_change = (abs_change / pre_mean * 100) if pre_mean != 0 else float("nan")

    pre_slope  = float(np.polyfit(pre_t,  pre_vals,  1)[0])
    post_slope = float(np.polyfit(post_t, post_vals, 1)[0])

    t_stat, p_val = stats.ttest_ind(pre_vals, post_vals, equal_var=False)
    significant = "yes" if p_val < 0.05 else "no"

    unit_map = {
        "temperature_c": "degC", "ph": "pH", "do_percent": "%",
        "biomass_gL": "g/L", "substrate_gL": "g/L",
        "product_titer_gL": "g/L", "feed_rate_Lh": "L/h",
    }
    unit = unit_map.get(column, "")

    return (
        f"Comparison of '{column}' around event '{event_name}' "
        f"(event window t=[{ev_start}, {ev_end}) h, comparison window +/-{window_h} h):\n"
        f"\n"
        f"  Pre-event   t=[{ev_start - window_h:.1f}, {ev_start:.1f}) h:\n"
        f"    mean  = {pre_mean:.4f} {unit}\n"
        f"    slope = {pre_slope:.5f} {unit}/h\n"
        f"\n"
        f"  Post-event t=[{ev_end:.1f}, {ev_end + window_h:.1f}) h:\n"
        f"    mean  = {post_mean:.4f} {unit}\n"
        f"    slope = {post_slope:.5f} {unit}/h\n"
        f"\n"
        f"  Change: {abs_change:+.4f} {unit} ({pct_change:+.1f}%)\n"
        f"  Welch t-test p={p_val:.2e}, statistically significant: {significant}"
    )
