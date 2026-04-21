"""Time-window slicing helpers shared across tools."""

import pandas as pd
from .loader import T_MAX

VALID_COLUMNS = {
    "temperature_c", "ph", "do_percent",
    "biomass_gL", "substrate_gL", "product_titer_gL", "feed_rate_Lh",
}


def slice_window(df: pd.DataFrame, t_start: float, t_end: float) -> pd.DataFrame:
    """Return rows where t_start <= t_hours < t_end.

    Raises ValueError if the window is invalid or produces no data.
    """
    if t_start >= t_end:
        raise ValueError(f"t_start ({t_start}) must be less than t_end ({t_end}).")
    if t_end < 0 or t_start > T_MAX:
        raise ValueError(
            f"Window [{t_start}, {t_end}) is entirely outside the dataset range [0, {T_MAX}]."
        )
    subset = df[(df["t_hours"] >= t_start) & (df["t_hours"] < t_end)].copy()
    if subset.empty:
        raise ValueError(f"No data found in window [{t_start}, {t_end}).")
    return subset


def validate_column(column: str) -> None:
    if column not in VALID_COLUMNS:
        raise ValueError(
            f"Unknown column '{column}'. Valid options: {sorted(VALID_COLUMNS)}"
        )
