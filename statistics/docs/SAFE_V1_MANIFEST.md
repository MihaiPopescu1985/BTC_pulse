# SAFE v1.0 Manifest

## Scope
SAFE v1 is a probabilistic market context engine.
It does NOT predict price. It allocates risk.

## Data
- Asset: BTC
- Frequency: Daily
- Period: 2017-11-24 → present

## Regime Model
- Model: Gaussian HMM
- States: K = 4
- Labels (semantic, derived):
  - CORE
  - DRIFT
  - SURGE
  - SHOCK
- Regimes are probabilistic and overlapping.
- HMM_DOM is a summary, not a discrete switch.

## Production Features (features.json)
Price:
- close
- TS_50
- band_w
- band_pos

Hazard:
- P_CORRECTION_10D
- P_REBOUND_10D

Regime:
- HMM_STATE_0..3
- HMM_DOM
- HMM_CONF

SAFE internal:
- entry_step_safe
- conviction_safe

## Experimental Features (features_extras.json)
- E_target_safe
- L_target_safe
- direction_safe
- range_score
- P_CORRECTION_10D_CAL
- P_REBOUND_10D_CAL

These are NOT used in SAFE v1 policy.

## Validation
- Feature contracts validated (pre / post HMM)
- Walk-forward backtests (no leakage)
- Feature permutation importance on CAGR

## Status
SAFE v1.0 — frozen
Any future changes must be versioned (v2.x).
