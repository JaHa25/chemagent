"""
Synthetic continuous bioreactor dataset generator.

Simulates 72 hours of an aerobic bioreactor producing mycoprotein at 1-minute
resolution. The dynamics are a simplified fed-batch model (not a full CSTR
mass balance): Monod growth coupled with a Luedeking-Piret-style yield term
for product formation. Three explicit operational events are injected:

  1. Feed adjustment    at t = 30 h        : substrate pulse, product slope up
  2. Oxygen limitation  at t = 38 h -> 42 h: DO dip, biomass/product plateau
  3. pH sensor drift    at t = 42 h -> 72 h: measured pH drifts upward
                                              (true pH remains controlled)

All event windows, magnitudes, and rates are defined in EVENTS below and are
the single source of truth used by events.csv and ground_truth.md.

Run:
    python data/generate_data.py

Outputs:
    data/bioreactor_timeseries.csv
    data/events.csv
"""

import numpy as np
import pandas as pd
from pathlib import Path

SEED = 42
DURATION_H = 72
DT_MIN = 1
OUT_DIR = Path(__file__).parent

# --- Event definitions (single source of truth) ---
EVENTS = [
    {
        "event_id": 1,
        "event_name": "feed_adjustment",
        "event_type": "process_change",
        "event_time_h": 30.0,
        "event_start_h": 30.0,
        "event_end_h": 34.0,
        "description": (
            "Feed rate stepped from 0.5 to 1.2 L/h at 30 h, then reduced to "
            "0.7 L/h at 34 h. Causes a substrate pulse and a steeper product "
            "formation slope."
        ),
    },
    {
        "event_id": 2,
        "event_name": "oxygen_limitation",
        "event_type": "disturbance",
        "event_time_h": 38.0,
        "event_start_h": 38.0,
        "event_end_h": 42.0,
        "description": (
            "Dissolved oxygen drops below 35 % saturation for ~4 h. Growth "
            "and product formation are suppressed during the limitation."
        ),
    },
    {
        "event_id": 3,
        "event_name": "ph_sensor_drift",
        "event_type": "sensor_fault",
        "event_time_h": 42.0,
        "event_start_h": 42.0,
        "event_end_h": 72.0,
        "description": (
            "pH probe drifts upward at ~0.008 pH units/h starting at 42 h. "
            "True process pH remains controlled; measured pH is unreliable."
        ),
    },
]

# Derived constants (kept in one place for ground-truth consistency)
PH_DRIFT_START_H = 42.0
PH_DRIFT_RATE = 0.008  # pH units per hour (upward)
FEED_STEP_UP_H = 30.0
FEED_STEP_DOWN_H = 34.0
FEED_BASE = 0.5
FEED_HIGH = 1.2
FEED_TAPER = 0.7
O2_DIP_AMP = 28.0  # % saturation


def make_time_index() -> np.ndarray:
    n = DURATION_H * 60 // DT_MIN + 1
    return np.linspace(0, DURATION_H, n)


def smooth_step(t: np.ndarray, t_on: float, t_off: float, amplitude: float) -> np.ndarray:
    """Sigmoid-shaped event window between t_on and t_off."""
    on = 1 / (1 + np.exp(-4 * (t - t_on)))
    off = 1 / (1 + np.exp(-4 * (t - t_off)))
    return amplitude * (on - off)


def generate_timeseries(rng: np.random.Generator) -> pd.DataFrame:
    t = make_time_index()
    n = len(t)

    # --- Temperature (°C) ---
    # Controlled at 35 °C with mild disturbances and sensor noise
    temperature = (
        35.0
        + 0.3 * np.sin(2 * np.pi * t / 24)
        + 0.15 * np.sin(2 * np.pi * t / 6)
        + rng.normal(0, 0.05, n)
    )
    # Small transient during O2 limitation (metabolic heat change)
    temperature += smooth_step(t, 38.0, 42.0, 0.4)

    # --- pH (true vs measured) ---
    # True process pH is tightly controlled at 6.8
    ph_true = (
        6.80
        + 0.05 * np.sin(2 * np.pi * t / 12)
        + rng.normal(0, 0.02, n)
    )
    # Measured pH = true pH + linear sensor drift after PH_DRIFT_START_H
    ph_drift = np.where(t > PH_DRIFT_START_H, PH_DRIFT_RATE * (t - PH_DRIFT_START_H), 0.0)
    ph_measured = ph_true + ph_drift

    # --- Dissolved oxygen (% saturation) ---
    do_percent = (
        65.0
        + 3.0 * np.sin(2 * np.pi * t / 8)
        + rng.normal(0, 0.8, n)
    )
    do_percent -= smooth_step(t, 38.0, 42.0, O2_DIP_AMP)
    do_percent = np.clip(do_percent, 5.0, 100.0)

    # --- Substrate concentration (g/L) ---
    substrate = (
        5.0
        + 3.0 * np.exp(-0.05 * t)
        + rng.normal(0, 0.15, n)
    )
    feed_mask = t >= FEED_STEP_UP_H
    substrate_feed = np.zeros(n)
    substrate_feed[feed_mask] = 6.0 * np.exp(-0.18 * (t[feed_mask] - FEED_STEP_UP_H))
    substrate += substrate_feed
    substrate = np.clip(substrate, 0.1, 30.0)

    # --- Biomass concentration (g/L) ---
    # Monod kinetics: dX/dt = mu * X, mu = mu_max * S / (K_s + S)
    # mu_max tuned so biomass grows gradually across the full 72 h (realistic
    # for mycoprotein fermentation): this preserves signal for the feed-
    # adjustment comparative query.
    mu_max = 0.06
    K_s = 0.5
    X_cap = 28.0
    biomass_smooth = np.zeros(n)
    biomass_smooth[0] = 2.0
    for i in range(1, n):
        dt = t[i] - t[i - 1]
        mu = mu_max * substrate[i - 1] / (K_s + substrate[i - 1])
        if 38.0 <= t[i] <= 42.0:
            mu *= 0.25
        biomass_smooth[i] = biomass_smooth[i - 1] + mu * biomass_smooth[i - 1] * dt
        biomass_smooth[i] = min(biomass_smooth[i], X_cap)
    biomass = biomass_smooth + rng.normal(0, 0.08, n)
    biomass = np.clip(biomass, 0.5, X_cap + 2.0)

    # --- Product titer (g/L) ---
    # Luedeking-Piret style growth-coupled product formation
    product_titer = np.zeros(n)
    product_titer[0] = 0.1
    yield_factor = 0.38
    for i in range(1, n):
        yf = yield_factor * (1.3 if t[i] >= FEED_STEP_UP_H else 1.0)
        if 38.0 <= t[i] <= 42.0:
            yf *= 0.1
        d_biomass = max(biomass_smooth[i] - biomass_smooth[i - 1], 0.0)
        product_titer[i] = product_titer[i - 1] + yf * d_biomass
    product_titer += rng.normal(0, 0.05, n)
    product_titer = np.clip(product_titer, 0.0, 50.0)

    # --- Feed rate (L/h) ---
    feed_rate = np.full(n, FEED_BASE)
    feed_rate[t >= FEED_STEP_UP_H] = FEED_HIGH
    feed_rate[t >= FEED_STEP_DOWN_H] = FEED_TAPER
    feed_rate += rng.normal(0, 0.02, n)
    feed_rate = np.clip(feed_rate, 0.0, 3.0)

    timestamps = pd.Timestamp("2026-01-01") + pd.to_timedelta(t, unit="h")

    df = pd.DataFrame({
        "timestamp": timestamps,
        "t_hours": np.round(t, 4),
        "temperature_c": np.round(temperature, 3),
        "ph": np.round(ph_measured, 4),
        "ph_true": np.round(ph_true, 4),
        "do_percent": np.round(do_percent, 3),
        "biomass_gL": np.round(biomass, 4),
        "substrate_gL": np.round(substrate, 4),
        "product_titer_gL": np.round(product_titer, 4),
        "feed_rate_Lh": np.round(feed_rate, 4),
    })
    return df


def generate_events() -> pd.DataFrame:
    cols = ["event_id", "event_name", "event_type",
            "event_time_h", "event_start_h", "event_end_h", "description"]
    return pd.DataFrame(EVENTS)[cols]


def main() -> None:
    rng = np.random.default_rng(SEED)
    ts = generate_timeseries(rng)
    events = generate_events()

    ts_path = OUT_DIR / "bioreactor_timeseries.csv"
    ev_path = OUT_DIR / "events.csv"

    ts.to_csv(ts_path, index=False)
    events.to_csv(ev_path, index=False)

    print(f"Generated {len(ts):,} rows -> {ts_path}")
    print(f"Generated {len(events)} events -> {ev_path}")
    print("\nDataset summary:")
    print(ts.describe().to_string())


if __name__ == "__main__":
    main()
