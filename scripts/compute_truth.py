"""Recomputes ground-truth numbers for data/ground_truth.md.

Run from the project root after regenerating the dataset.
"""
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
df = pd.read_csv(DATA_DIR / "bioreactor_timeseries.csv")

def win(a, b):
    return df[(df.t_hours >= a) & (df.t_hours < b)]

def row(label, series):
    print(f"{label:40s}  mean={series.mean():.3f}  min={series.min():.3f}  max={series.max():.3f}  std={series.std():.3f}  n={len(series)}")

print("=== Descriptive ===")
row("pH (measured) last 12h [60-72]", win(60, 72).ph)
row("pH (true) last 12h [60-72]",     win(60, 72).ph_true)
row("Biomass max 20-36h",              win(20, 36).biomass_gL)
row("DO min 0-24h",                    win(0, 24).do_percent)

print("\n=== Diagnostic windows ===")
row("Temperature 24-72h",              win(24, 72).temperature_c)
row("Temperature during O2 38-42h",    win(38, 42).temperature_c)
row("DO 36-44h (around O2 event)",     win(36, 44).do_percent)
row("pH (measured) 42-72h",            win(42, 72).ph)
row("pH (true) 42-72h",                win(42, 72).ph_true)

print("\n=== Comparative (pre/post feed adjustment at 30h) ===")
row("Product titer 24-30h (pre)",      win(24, 30).product_titer_gL)
row("Product titer 30-36h (post)",     win(30, 36).product_titer_gL)
# slope via linear fit
import numpy as np
for a, b, label in [(24, 30, "pre-feed slope"), (30, 36, "post-feed slope")]:
    w = win(a, b)
    slope = np.polyfit(w.t_hours, w.product_titer_gL, 1)[0]
    print(f"{label:40s}  slope={slope:.4f} g/L/h")

print("\n=== Comparative (pre/post O2 limitation at 38-42h) ===")
row("Substrate 34-38h (pre)",          win(34, 38).substrate_gL)
row("Substrate 42-46h (post)",         win(42, 46).substrate_gL)
row("Biomass 34-38h (pre)",            win(34, 38).biomass_gL)
row("Biomass 42-46h (post)",           win(42, 46).biomass_gL)

print("\n=== pH drift diagnosis ===")
tail = win(60, 72)
print(f"Measured pH mean 60-72h: {tail.ph.mean():.3f}")
print(f"True pH mean 60-72h:     {tail.ph_true.mean():.3f}")
print(f"Drift at t=72h (measured-true): {(tail.ph - tail.ph_true).mean():.3f}")
