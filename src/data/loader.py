"""
Loads the bioreactor dataset from CSV.

ph_true is stripped before returning: it is a ground-truth evaluation column
and must not be visible to the agent.
"""

from pathlib import Path
import pandas as pd

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_AGENT_COLUMNS = [
    "timestamp", "t_hours", "temperature_c", "ph",
    "do_percent", "biomass_gL", "substrate_gL",
    "product_titer_gL", "feed_rate_Lh",
]

T_MAX: float = 72.0  # total dataset duration in hours

_ts_cache: pd.DataFrame | None = None
_ev_cache: pd.DataFrame | None = None


def load_timeseries() -> pd.DataFrame:
    """Return the bioreactor time-series without the ground-truth ph_true column."""
    global _ts_cache
    if _ts_cache is None:
        path = _DATA_DIR / "bioreactor_timeseries.csv"
        if not path.exists():
            raise FileNotFoundError(f"Dataset not found at {path}. Run data/generate_data.py first.")
        df = pd.read_csv(path, parse_dates=["timestamp"])
        _ts_cache = df[_AGENT_COLUMNS].copy()
    return _ts_cache


def load_events() -> pd.DataFrame:
    """Return the events table."""
    global _ev_cache
    if _ev_cache is None:
        path = _DATA_DIR / "events.csv"
        if not path.exists():
            raise FileNotFoundError(f"Events file not found at {path}. Run data/generate_data.py first.")
        _ev_cache = pd.read_csv(path)
    return _ev_cache
