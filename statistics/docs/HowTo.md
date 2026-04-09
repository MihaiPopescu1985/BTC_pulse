# State-Aware Feature Engine (SAFE)

## Prepare

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Repository layout

This repository is BTC-specific.

Productive execution path:
- `src/core/`

Archived research / descriptive v4 iteration:
- `src/research/v4_iteration/`

Accepted validation path:
- `src/walkforward/`

Utilities remain unchanged:
- `src/util/`

Default inputs are read from `../data` relative to `src`:

- `../data/daily_price.json`
- `../data/daily_amounts.json`
- `../data/daily_tx_size.json`

Default outputs are written under `../out` relative to `src`:

- `../out/features.csv`
- `../out/onchain_features.csv`
- `../out/targets.csv`
- `../out/models/hmm_pack.joblib`
- `../out/models/hazard_pack.joblib`

---

## First-time setup (build everything from scratch)

Use this when running the project for the first time or after deleting model artifacts.

```bash
source .venv/bin/activate

python src/data/query.py
python src/core/run_features.py
python src/core/run_regime_hmm.py --retrain-hmm
python src/core/run_hazard_train.py
python src/core/run_exposure.py
python src/core/run_onchain_features.py
python src/core/run_targets.py
python src/core/run_states.py
python src/walkforward/run_decision_analysis_walkforward.py
python src/walkforward/run_policy_backtest_walkforward.py
```

This will:
- generate descriptive features
- train HMM model
- train hazard model
- compute exposure
- build explicit market states
- compute forward truth-layer targets
- build the productive walk-forward decision layer
- run the accepted walk-forward policy proof
- generate all outputs in `../out`

---

## Productive BTC pipeline

### Daily run (apply existing models)

Use this for normal daily updates. This does **not retrain models**.

```bash
source .venv/bin/activate

python src/data/query.py
python src/core/run_onchain_features.py
python src/core/run_exposure.py

# python -m http.server 8000
# then open:
# http://localhost:8000/viewer/dashboard.html
```

Requirements:
- `../out/models/hmm_pack.joblib` must already exist
- `../out/models/hazard_pack.joblib` must already exist

---

### Accepted walk-forward SAFE v4.0 validation path

Use this to reproduce the accepted leakage-free SAFE v4.0 validation branch.
This is not the daily live-update surface.

```bash
source .venv/bin/activate

python src/core/run_targets.py
python src/core/run_states.py
python src/walkforward/run_decision_analysis_walkforward.py
python src/walkforward/run_policy_backtest_walkforward.py
python src/walkforward/run_policy_refinement_walkforward.py
python src/walkforward/run_policy_stress_walkforward.py
```

This is the accepted productive validation path.

---

### Refit / refresh models (periodic)

Use this when you want to retrain models on updated data.

```bash
source .venv/bin/activate

python src/data/query.py
python src/core/run_features.py
python src/core/run_regime_hmm.py --retrain-hmm
python src/core/run_hazard_train.py
python src/core/run_exposure.py
python src/core/run_onchain_features.py
python src/core/run_targets.py
python src/core/run_states.py
python src/walkforward/run_decision_analysis_walkforward.py
python src/walkforward/run_policy_backtest_walkforward.py
python src/walkforward/run_policy_refinement_walkforward.py
python src/walkforward/run_policy_stress_walkforward.py
```

Notes:
- HMM is retrained explicitly via `--retrain-hmm`
- Hazard is retrained every time `run_hazard_train.py` is executed
- Exposure is recomputed after model refresh

---

## Stage responsibilities

- `src/core/run_features.py`
  - builds descriptive BTC OHLCV features

- `src/core/run_regime_hmm.py`
  - fits/applies the HMM regime model
  - writes `../out/models/hmm_pack.joblib`

- `src/core/run_hazard_train.py`
  - trains calibrated hazard models
  - writes `../out/models/hazard_pack.joblib`

- `src/core/run_exposure.py`
  - applies HMM + hazard + exposure logic
  - writes the consolidated `../out/features.csv`
  - uses `src/core/exposure.py` as productive exposure-targeting logic

- `src/core/run_onchain_features.py`
  - builds descriptive on-chain features
  - writes `../out/onchain_features.csv`

- `src/core/run_targets.py`
  - builds forward outcome labels for validation and analysis only
  - writes `../out/targets.csv`
  - must not be used as live predictive input

- `src/core/run_states.py`
  - builds explicit HMM-derived and rule-based market states
  - writes `../out/states.csv`

- `src/walkforward/run_decision_analysis_walkforward.py`
  - builds the accepted leakage-free decision-validation layer
  - writes `../out/decision_analysis_walkforward.csv`

- `src/walkforward/run_policy_backtest_walkforward.py`
  - runs the accepted leakage-free policy proof
  - writes `../out/policy_backtest_walkforward.csv`

- `src/walkforward/run_policy_refinement_walkforward.py`
  - runs the accepted walk-forward ablation/refinement layer
  - writes `../out/policy_refinement_walkforward.csv`

- `src/walkforward/run_policy_stress_walkforward.py`
  - runs the accepted walk-forward robustness/stress layer
  - writes `../out/policy_stress_walkforward.csv`

---

## Research surface

These scripts remain outside the productive top-level execution surface. They now live in three research layers:

- `core/`: stable research building blocks
- `research_active/`: currently active research scripts
- `research_archive/`: older or not-currently-used research scripts

- `src/research/v4_iteration/core/indicator_audit/run_indicator_reliability.py`
- `src/research/v4_iteration/research_archive/run_feature_redundancy.py`
- `src/research/v4_iteration/research_archive/run_calibration.py`
- `src/research/v4_iteration/research_active/run_state_outcomes.py`
- `src/research/v4_iteration/research_active/run_decision_analysis.py`
- `src/research/v4_iteration/research_archive/run_decision_validation.py`
- `src/research/v4_iteration/research_active/run_policy_backtest.py`
- `src/research/v4_iteration/research_archive/safe_interpreter.py`
- `src/research/v4_iteration/research_active/safe_interpreter_v2.py`

---

## Data retrieval surface

BTC data retrieval and export now live under `src/data/`:

- `src/data/query.py`
  - updates local BTC raw inputs under `statistics/data`

- `src/data/binance.py`
  - fetches daily BTC/USDT candles from Binance

- `src/data/loaders.py`
  - validates and loads local BTC daily OHLCV

## Useful utilities

### Print a recent feature window

```bash
python src/util/print_features_range.py 2026-03-09 2026-03-12 --path ../out/features.csv >> daily_reading.txt
python src/util/print_features_range.py 2026-03-09 2026-03-12 --path ../out/onchain_features.csv >> daily_reading.txt
```

---

### Regime-conditioned touch probabilities

```bash
python src/util/safe_touch_probabilities.py \
  --date 2026-03-12 \
  --days 10 \
  --sims 20000 >> daily_reading.txt
```

---
