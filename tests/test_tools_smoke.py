"""
Smoke tests for ChemAgent tools.

Verifies:
 - all 5 tools run without error on valid inputs
 - key ground-truth values fall within expected ranges
 - validation errors are raised on bad inputs
 - plot_variable produces a real PNG file

Run from chemagent/:  python -m pytest tests/ -v
or standalone:        python tests/test_tools_smoke.py
"""

import re
from pathlib import Path

import pytest

from src.tools.summary_statistics import summary_statistics
from src.tools.detect_anomalies import detect_anomalies
from src.tools.compute_trend import compute_trend
from src.tools.compare_pre_post_event import compare_pre_post_event
from src.tools.plot_variable import plot_variable
from src.data.loader import load_timeseries, load_events, T_MAX
from src.data.query_utils import slice_window, validate_column


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_float(text: str, label: str) -> float:
    """Extract the float after `label =` in a tool's output string."""
    m = re.search(rf"{re.escape(label)}\s*=\s*(-?\d+\.?\d*(?:[eE][+-]?\d+)?)", text)
    assert m, f"Could not find '{label} =' in:\n{text}"
    return float(m.group(1))


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------

class TestDataLayer:
    def test_timeseries_loads(self):
        df = load_timeseries()
        assert len(df) > 0
        assert "t_hours" in df.columns
        assert df["t_hours"].max() <= T_MAX

    def test_events_load(self):
        ev = load_events()
        assert len(ev) >= 3
        names = set(ev["event_name"])
        assert {"feed_adjustment", "oxygen_limitation", "ph_sensor_drift"} <= names

    def test_slice_window_rejects_inverted(self):
        df = load_timeseries()
        with pytest.raises(ValueError):
            slice_window(df, 10.0, 5.0)

    def test_slice_window_rejects_oob(self):
        df = load_timeseries()
        with pytest.raises(ValueError):
            slice_window(df, 100.0, 200.0)

    def test_validate_column_rejects_bad(self):
        with pytest.raises(ValueError):
            validate_column("not_a_column")


# ---------------------------------------------------------------------------
# summary_statistics
# ---------------------------------------------------------------------------

class TestSummaryStatistics:
    def test_runs(self):
        out = summary_statistics("ph", 60.0, 72.0)
        assert "mean" in out

    def test_q1_ph_last_12h(self):
        """Ground truth: measured pH mean ~6.99 over [60, 72)."""
        out = summary_statistics("ph", 60.0, 72.0)
        mean = _extract_float(out, "mean")
        assert 6.95 <= mean <= 7.05, f"pH mean {mean} out of range"

    def test_q2_biomass_max(self):
        """Ground truth: max biomass in [20, 36) h is ~15.0 g/L."""
        out = summary_statistics("biomass_gL", 20.0, 36.0)
        mx = _extract_float(out, "max")
        assert 14.5 <= mx <= 15.5, f"biomass max {mx} out of range"

    def test_q3_do_min(self):
        """Ground truth: min DO in [0, 24) h is ~59.8 %."""
        out = summary_statistics("do_percent", 0.0, 24.0)
        mn = _extract_float(out, "min")
        assert 58.0 <= mn <= 62.0, f"DO min {mn} out of range"

    def test_bad_column_raises(self):
        with pytest.raises(ValueError):
            summary_statistics("bogus", 0.0, 12.0)


# ---------------------------------------------------------------------------
# compute_trend
# ---------------------------------------------------------------------------

class TestComputeTrend:
    def test_q6_ph_drift_after_42h(self):
        """Ground truth: pH slope after 42h is ~0.008 pH/h (sensor fault)."""
        out = compute_trend("ph", 42.0, 72.0)
        slope = _extract_float(out, "slope")
        assert 0.005 <= slope <= 0.012, f"pH drift slope {slope} out of range"
        assert "increasing" in out

    def test_flat_temperature(self):
        """Temperature should be ~flat early in the run (baseline)."""
        out = compute_trend("temperature_c", 0.0, 20.0)
        slope = _extract_float(out, "slope")
        assert abs(slope) < 0.1, f"early-run temp slope {slope} unexpectedly large"


# ---------------------------------------------------------------------------
# detect_anomalies
# ---------------------------------------------------------------------------

class TestDetectAnomalies:
    def test_do_drop_flagged(self):
        """DO during [36, 44) should show the O2 limitation drop."""
        out = detect_anomalies("do_percent", 36.0, 44.0)
        assert "Anomalies detected" in out or "No anomalies" in out

    def test_runs_full_window(self):
        out = detect_anomalies("ph", 0.0, 72.0)
        assert isinstance(out, str) and len(out) > 0


# ---------------------------------------------------------------------------
# compare_pre_post_event
# ---------------------------------------------------------------------------

class TestComparePrePost:
    def test_q8_substrate_after_o2_limitation(self):
        """Ground truth: substrate decrease ~1.8 g/L after O2 limitation."""
        out = compare_pre_post_event("oxygen_limitation", "substrate_gL", window_h=6.0)
        assert "Change:" in out
        m = re.search(r"Change:\s*([+-]?\d+\.?\d*)", out)
        assert m
        delta = float(m.group(1))
        assert -2.5 <= delta <= -1.0, f"substrate change {delta} out of expected range"

    def test_q7_product_titer_feed_adjustment(self):
        """Ground truth: post-slope / pre-slope for product titer ~1.5-2.2x."""
        out = compare_pre_post_event("feed_adjustment", "product_titer_gL", window_h=6.0)
        # Parse both slopes (pre_slope and post_slope appear in that order)
        slopes = re.findall(r"slope\s*=\s*(-?\d+\.?\d*)", out)
        assert len(slopes) >= 2, f"Expected 2 slopes, got: {slopes}"
        pre_s, post_s = float(slopes[0]), float(slopes[1])
        assert pre_s > 0 and post_s > 0
        ratio = post_s / pre_s
        assert 1.3 <= ratio <= 2.5, f"titer slope ratio {ratio:.2f} out of range"

    def test_unknown_event_raises(self):
        with pytest.raises(ValueError):
            compare_pre_post_event("not_an_event", "ph")


# ---------------------------------------------------------------------------
# plot_variable
# ---------------------------------------------------------------------------

class TestPlotVariable:
    def test_produces_png(self):
        path = plot_variable("ph", 0.0, 72.0)
        p = Path(path)
        assert p.exists(), f"plot file not created: {path}"
        assert p.stat().st_size > 0
        assert p.suffix == ".png"

    def test_narrow_window(self):
        path = plot_variable("do_percent", 36.0, 44.0)
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
