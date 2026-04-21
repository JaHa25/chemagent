"""Look up event windows by name from events.csv."""

from .loader import load_events

_events_index: object = None  # cached indexed DataFrame


def _get_index():
    global _events_index
    if _events_index is None:
        _events_index = load_events().set_index("event_name")
    return _events_index


def get_event_window(event_name: str) -> tuple[float, float]:
    """Return (start_h, end_h) for a named event."""
    idx = _get_index()
    if event_name not in idx.index:
        raise ValueError(
            f"Unknown event '{event_name}'. Valid events: {sorted(idx.index.tolist())}"
        )
    row = idx.loc[event_name]
    return float(row["event_start_h"]), float(row["event_end_h"])


def list_events() -> list[dict]:
    """Return a list of event dicts with name, type, start_h, end_h, description."""
    return (
        _get_index()
        .reset_index()[["event_name", "event_type", "event_start_h", "event_end_h", "description"]]
        .to_dict(orient="records")
    )
