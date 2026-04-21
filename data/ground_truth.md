# Ground Truth Reference

Authoritative expected values for the evaluation query set, computed directly
from the synthetic dataset (seed = 42) with known event windows. Use this
file to score agent responses objectively.

All numeric intervals are `[start, end)` in process time `t_hours`.

---

## Event windows (authoritative)

| Event | Window | Effect summary |
|---|---|---|
| Feed adjustment | [30.0, 34.0) h (step-up), feed tapered at 34.0 h | Substrate pulse peaking ~12 g/L; product slope ~1.9× steeper; feed-rate 0.5 → 1.2 → 0.7 L/h |
| O₂ limitation | [38.0, 42.0) h | DO dips to ~34 % saturation; biomass/product growth suppressed ~75 %; small transient +0.4 °C temperature bump |
| pH sensor drift | [42.0, 72.0) h | Measured pH drifts at +0.008 pH/h; true process pH stays at 6.80 ± 0.05 |

---

## Evaluation queries — expected answers

### Descriptive

**Q1.** *What was the average pH over the last 12 hours?*
- Window: [60.0, 72.0) h
- **Measured pH**: mean ≈ **6.99**, min 6.91, max 7.10
- **True pH** (for diagnosis): mean 6.80
- **Verdict rule:** correct if agent returns a value in [6.95, 7.05] *and* flags that the reading is contaminated by sensor drift. Partial if only the number is correct.

**Q2.** *What was the maximum biomass concentration between 20 h and 36 h?*
- Window: [20.0, 36.0) h
- **Expected max**: ≈ **15.0 g/L** (around t = 36 h)
- **Verdict rule:** correct if in [14.5, 15.5] g/L.

**Q3.** *What was the minimum dissolved oxygen in the first 24 hours?*
- Window: [0.0, 24.0) h
- **Expected min**: ≈ **59.8 %**
- **Verdict rule:** correct if in [58.0, 62.0] %. Note: true low-DO event is later (t ≈ 38–42 h), so this answer should *not* mention the O₂ limitation.

### Diagnostic

**Q4.** *Were there any temperature anomalies after 24 h?*
- **Expected**: a small, transient bump of ~+0.4 °C during the O₂ limitation window [38, 42) h is detectable but not a true anomaly in the control sense.
- **Verdict rule:** correct if agent reports *no large anomalies* and optionally notes the minor transient coinciding with the O₂ event. Incorrect if it fabricates an anomaly elsewhere.

**Q5.** *Did dissolved oxygen show an unusual drop near 38 h?*
- **Expected**: yes — DO dropped from ~65 % baseline to a minimum of ~**33.7 %** during [38, 42) h, a drop of ≈ 31 percentage points.
- **Verdict rule:** correct if agent identifies the dip, locates it in [37, 43) h, and gives a drop magnitude ≥ 25 pp.

**Q6.** *Was there evidence of pH drift after 42 h?*
- **Expected**: yes — measured pH drifts upward at ≈ 0.008 pH/h; cumulative offset at t = 72 h is ≈ **+0.19 pH**.
- True pH remains controlled at ≈ 6.80. This is a **sensor fault**, not a process change.
- **Verdict rule:** correct if agent (a) identifies an upward trend/drift starting near 42 h and (b) characterises it as a probable sensor issue rather than an actual process shift. Partial if only (a).

### Comparative

**Q7.** *How did product titer change before and after the feed adjustment?*
- Pre-window [24, 30) h: mean = 2.78 g/L, slope ≈ **0.19 g/L/h**
- Post-window [30, 36) h: mean = 4.39 g/L, slope ≈ **0.35 g/L/h**
- **Expected**: product formation rate increased by roughly **1.8×** after the feed adjustment.
- **Verdict rule:** correct if agent reports a clear acceleration / steeper slope, with the post/pre ratio in [1.5×, 2.2×]. Partial if direction correct but magnitude wrong.

**Q8.** *How did substrate concentration change after the oxygen limitation event?*
- Pre-window [34, 38) h: mean = **7.59 g/L**
- Post-window [42, 46) h: mean = **5.83 g/L**
- **Expected**: substrate decreased by ≈ **1.8 g/L** (~23 %) across the event, consistent with accumulated consumption and diminishing feed pulse.
- **Verdict rule:** correct if agent reports a decrease of 1.3–2.3 g/L. Partial if direction only.

---

## Notes on scoring

- **Numerical tolerances** above assume the default seed (42). If the seed is changed, re-run `data/_compute_truth.py` to refresh these numbers.
- **Diagnosis beats arithmetic.** For Q1 and Q6, an agent that computes the drift-contaminated number but *fails to flag the sensor fault* should score partial, not correct.
- **Window alignment.** Agents are allowed to choose windows of their own length but must justify the choice. If an agent uses e.g. [24, 30) vs [30, 36) for Q7, accept; [20, 30) vs [30, 40) is also acceptable if the magnitudes are still in tolerance.
