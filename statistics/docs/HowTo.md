# State-Aware Feature Engine (SAFE)

## Prepare

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Repository layout

This repository is BTC-specific.

- productive pipeline: `src/core/`
- data access: `src/data/`
- feature logic: `src/features/`
- models: `src/models/`
- utilities: `src/util/`
- retained research core: `src/research/v4_iteration/core/`

Default inputs:

- `data/daily_price.json`
- `data/daily_amounts.json`
- `data/daily_tx_size.json`

Primary retained outputs:

- `out/features.csv`
- `out/onchain_features.csv`
- `out/targets.csv`
- `out/states.csv`
- `out/models/hmm_pack.joblib`
- `out/models/hazard_pack.joblib`
- `out/swing_detection/swings.csv`
- `out/swing_detection/swing_sensitivity_summary.csv`
- `out/swing_bridge/live_swing_state.csv`
- `out/swing_bridge/swing_taxonomy.csv`
- `out/swing_bridge/swing_condition_mapping.csv`

## Productive BTC pipeline

### Full rebuild

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
```

This rebuilds the retained productive feature, model, target, and state surface.

### Daily refresh

```bash
source .venv/bin/activate

python src/data/query.py
python src/core/run_onchain_features.py
python src/core/run_exposure.py
```

Requirements:

- `out/models/hmm_pack.joblib` must exist
- `out/models/hazard_pack.joblib` must exist

## Retained research foundation

### Indicator audit

```bash
source .venv/bin/activate
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/indicator_audit/run_indicator_reliability.py
```

### Interaction discovery

```bash
source .venv/bin/activate
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/interaction_discovery/run_interaction_discovery.py
```

### Swing detection

```bash
source .venv/bin/activate
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/swing_detection/run_swing_detection.py
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/swing_detection/run_swing_sensitivity.py
```

### Swing bridge

```bash
source .venv/bin/activate
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/swing_bridge/run_live_swing_state.py
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/swing_bridge/run_swing_taxonomy.py
PYTHONPATH=statistics python statistics/src/research/v4_iteration/core/swing_bridge/run_swing_condition_mapping.py
```

## Stage responsibilities

- `src/core/run_features.py`
  - builds BTC OHLCV features
- `src/core/run_regime_hmm.py`
  - fits or applies the HMM regime model
- `src/core/run_hazard_train.py`
  - trains calibrated hazard models
- `src/core/run_exposure.py`
  - applies HMM, hazard, and SAFE exposure logic
- `src/core/run_onchain_features.py`
  - builds retained on-chain features
- `src/core/run_targets.py`
  - builds forward research labels
- `src/core/run_states.py`
  - builds explicit market states
- `src/research/v4_iteration/core/indicator_audit/`
  - family-by-family indicator audit and reliability checks
- `src/research/v4_iteration/core/interaction_discovery/`
  - interaction templates and trend-state research
- `src/research/v4_iteration/core/swing_detection/`
  - volatility-normalized swing extraction and sensitivity checks
- `src/research/v4_iteration/core/swing_bridge/`
  - live swing state, swing taxonomy, and condition-to-swing mapping

## Viewer

The retained dashboard still supports the remaining swing work.

```bash
python -m http.server 8000
```

Then open:

- `http://localhost:8000/statistics/viewer/dashboard.html`
