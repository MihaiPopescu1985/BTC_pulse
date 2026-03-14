import json
import math
from collections import defaultdict

PATH = "out/btc/features.json"

EPS = 1e-6

def die(msg):
    raise SystemExit(f"[FAIL] {msg}")

def ok(msg):
    print(f"[OK] {msg}")

with open(PATH, "r") as f:
    data = json.load(f)

dates = data.get("dates")
series = data.get("series")

# ---------- A) Contract de date ----------
required_series = [
    "close",
    "HMM_STATE_0", "HMM_STATE_1", "HMM_STATE_2", "HMM_STATE_3",
    "HMM_CONF", "HMM_DOM",
    "P_CORRECTION_10D", "P_REBOUND_10D"
]

if not dates or not isinstance(dates, list):
    die("dates missing or invalid")

N = len(dates)

for k in required_series:
    if k not in series:
        die(f"missing required series: {k}")
    if len(series[k]) != N:
        die(f"length mismatch for {k}: {len(series[k])} vs dates {N}")

ok("All required series exist and lengths match")

# ---------- B) Probabilistic consistency ----------
for i in range(N):
    probs = [
        series["HMM_STATE_0"][i],
        series["HMM_STATE_1"][i],
        series["HMM_STATE_2"][i],
        series["HMM_STATE_3"][i],
    ]

    if any(p < -EPS or p > 1 + EPS for p in probs):
        die(f"probability out of bounds at index {i}")

    s = sum(probs)
    if not math.isclose(s, 1.0, abs_tol=1e-4):
        die(f"HMM prob sum != 1 at index {i}: {s}")

    conf = series["HMM_CONF"][i]
    dom = series["HMM_DOM"][i]

    if not math.isclose(conf, max(probs), abs_tol=1e-6):
        die(f"HMM_CONF mismatch at index {i}")

    if dom != probs.index(max(probs)):
        die(f"HMM_DOM mismatch at index {i}")

ok("HMM probabilities, CONF and DOM are consistent")

# ---------- C) Distribution sanity ----------
dom_counts = defaultdict(int)
conf_vals = []

for i in range(N):
    dom_counts[int(series["HMM_DOM"][i])] += 1
    conf_vals.append(series["HMM_CONF"][i])

print("\n--- Regime dominance distribution ---")
for k in sorted(dom_counts):
    print(f"State {k}: {dom_counts[k]} days ({dom_counts[k]/N:.1%})")

conf_vals_sorted = sorted(conf_vals)
def pct(p):
    return conf_vals_sorted[int(p * len(conf_vals_sorted))]

print("\n--- HMM_CONF distribution ---")
print(f"Median : {pct(0.50):.3f}")
print(f"P90    : {pct(0.90):.3f}")
print(f"P99    : {pct(0.99):.3f}")

ok("Distribution checks complete")

print("\n[SUCCESS] SAFE feature contract validated.")
