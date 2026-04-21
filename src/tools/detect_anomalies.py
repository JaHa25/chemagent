"""
Tool: detect_anomalies

Detects anomalies and sustained drift using a rolling z-score.
A point is flagged when |z| > threshold for at least min_consecutive samples,
which avoids false positives from single-point noise spikes.
"""

import numpy as np
from smolagents import tool
from ..data.loader import load_timeseries
from ..data.query_utils import slice_window, validate_column


@tool
def detect_anomalies(
    column: str,
    t_start: float,
    t_end: float,
    window_minutes: int = 60,
    z_threshold: float = 3.0,
    min_consecutive: int = 5,
) -> str:
    """Detect anomalies or sustained drift in a process variable using a rolling z-score.

    A flagged region is reported only when the z-score exceeds the threshold for
    at least min_consecutive consecutive samples: this avoids noise spikes being
    reported as anomalies.

    Args:
        column: Process variable to check. One of: temperature_c, ph,
            do_percent, biomass_gL, substrate_gL, product_titer_gL, feed_rate_Lh.
        t_start: Start of analysis window in process hours (inclusive).
        t_end: End of analysis window in process hours (exclusive).
        window_minutes: Rolling baseline window size in minutes (default 60).
            Larger values are better for detecting slow drift; smaller values
            catch sharper transients.
        z_threshold: Number of standard deviations to flag as anomalous (default 3.0).
        min_consecutive: Minimum consecutive flagged samples to report a region
            (default 5, i.e. 5 minutes at 1-min resolution).

    Returns:
        A plain-text report listing anomalous regions with time range, mean z-score,
        and peak deviation, or a confirmation that no anomalies were found.
    """
    validate_column(column)
    df = load_timeseries()
    window = slice_window(df, t_start, t_end)

    series = window[column].reset_index(drop=True)
    t = window["t_hours"].reset_index(drop=True)

    roll_mean = series.rolling(window_minutes, min_periods=max(1, window_minutes // 2), center=True).mean()
    roll_std  = series.rolling(window_minutes, min_periods=max(1, window_minutes // 2), center=True).std()

    # Avoid division by zero on constant segments
    roll_std = roll_std.replace(0, np.nan).fillna(series.std())
    z = (series - roll_mean) / roll_std

    flagged = z.abs() > z_threshold

    # Group consecutive flagged samples into regions
    regions = []
    in_region = False
    start_idx = None
    for i, flag in enumerate(flagged):
        if flag and not in_region:
            in_region = True
            start_idx = i
        elif not flag and in_region:
            in_region = False
            if i - start_idx >= min_consecutive:
                regions.append((start_idx, i - 1))
    if in_region and len(flagged) - start_idx >= min_consecutive:
        regions.append((start_idx, len(flagged) - 1))

    if not regions:
        return (
            f"No anomalies detected in '{column}' over t=[{t_start}, {t_end}) h "
            f"(rolling window={window_minutes} min, |z|>{z_threshold}, "
            f"min_consecutive={min_consecutive})."
        )

    lines = [
        f"Anomalies detected in '{column}' over t=[{t_start}, {t_end}) h "
        f"(rolling window={window_minutes} min, |z|>{z_threshold}):\n"
    ]
    for s_idx, e_idx in regions:
        t_s = round(float(t.iloc[s_idx]), 2)
        t_e = round(float(t.iloc[e_idx]), 2)
        z_mean = round(float(z.iloc[s_idx:e_idx + 1].abs().mean()), 2)
        z_peak = round(float(z.iloc[s_idx:e_idx + 1].abs().max()), 2)
        lines.append(
            f"  t=[{t_s}, {t_e}] h: mean |z|={z_mean}, peak |z|={z_peak} "
            f"({e_idx - s_idx + 1} samples)"
        )

    return "\n".join(lines)
