# Data Dictionary — ChemAgent Synthetic Bioreactor Dataset

## Process description

A simulated aerobic bioreactor producing mycoprotein (or comparable biomass
product). The underlying dynamic model is a simplified fed-batch description
— Monod growth kinetics coupled with a Luedeking-Piret-style growth-coupled
product formation term. It is not a full continuous-reactor mass balance:
there is no explicit dilution/outflow term, and product accumulates in the
vessel. This is acceptable for the purposes of this project (the brief
allows synthetic data and focuses on agentic analysis, not process control).

- **Duration:** 72 h
- **Sampling interval:** 1 min
- **Total samples:** 4,321
- **Random seed:** 42 (fully reproducible from `generate_data.py`)

---

## `bioreactor_timeseries.csv`

| Column | Unit | Description | Nominal / range |
| --- | --- | --- | --- |
| `timestamp` | ISO 8601 | Wall-clock timestamp (starts 2026-01-01 00:00:00) | — |
| `t_hours` | h | Elapsed process time | 0.0 – 72.0 |
| `temperature_c` | °C | Reactor temperature (measured) | ~35 ± 0.3 |
| `ph` | pH | **Measured** pH (contaminated by sensor drift after t = 42 h) | 6.7 – 7.1 |
| `ph_true` | pH | **True** process pH (ground truth — not available to a real operator) | 6.75 – 6.85 |
| `do_percent` | % saturation | Dissolved oxygen | ~65, dips to ~35 during O₂ limitation |
| `biomass_gL` | g/L | Biomass concentration | 2 → 22 (plateau) |
| `substrate_gL` | g/L | Carbon substrate concentration | 5 – 12 (spike at t = 30 h) |
| `product_titer_gL` | g/L | Product titer (accumulated) | 0 → ~7.7 |
| `feed_rate_Lh` | L/h | Substrate feed rate (step changes at events) | 0.5 / 1.2 / 0.7 |

### Controlled variables and setpoints

| Variable | Setpoint | Control tightness |
| --- | --- | --- |
| Temperature | 35 °C | ±0.3 °C typical |
| pH (true) | 6.80 | ±0.05 pH typical |
| DO | ≥ 60 % | Loses control during O₂ limitation event |

### ⚠️ `ph_true` is a ground-truth column

`ph_true` is present only so we can evaluate whether the agent correctly
diagnoses the pH sensor fault. **Do not expose it to the agent.** A real
operator would only see `ph`.

---

## `events.csv`

| Column | Description |
| --- | --- |
| `event_id` | Integer identifier |
| `event_name` | Short machine-readable name (`feed_adjustment`, `oxygen_limitation`, `ph_sensor_drift`) |
| `event_type` | One of `process_change`, `disturbance`, `sensor_fault` |
| `event_time_h` | Nominal event time (legacy / point reference) |
| `event_start_h` | Start of event window |
| `event_end_h` | End of event window (= simulation end for ongoing faults) |
| `description` | Human-readable narrative of cause and effect |

---

## Kinetic model (for reference)

- **Biomass:** dX/dt = μ·X, where μ = μ_max·S/(K_s + S), with μ_max = 0.18 h⁻¹, K_s = 0.5 g/L. Capped at X_max = 22 g/L. Growth rate multiplied by 0.25 during O₂ limitation.
- **Product:** dP/dt = Y_p/x · dX/dt, with Y_p/x = 0.38 g/g (×1.3 after feed adjustment, ×0.1 during O₂ limitation).
- **Substrate:** phenomenological — exponential decay + exponentially-decaying pulse at feed event. No full mass balance.
- **Temperature, pH (true), DO:** sinusoidal disturbances + Gaussian sensor noise, with sigmoidal event perturbations overlaid.
- **pH sensor drift:** measured_pH = true_pH + 0.008 · max(t − 42, 0).
