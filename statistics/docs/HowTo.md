# How To

## Prepare

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Repository layout

This repository is BTC-specific.

Default inputs are read from `../data` relative to `src`:

- `../data/daily_price.json`
- `../data/daily_amounts.json`
- `../data/daily_tx_size.json`

Default outputs are written under `../out` relative to `src`:

- `../out/features.csv`
- `../out/onchain_features.csv`
- `../out/models/hmm_pack.joblib`
- `../out/models/hazard_pack.joblib`

---

## First-time setup (build everything from scratch)

Use this when running the project for the first time or after deleting model artifacts.

```bash
source .venv/bin/activate

python src/crawler/query.py
python src/run_features.py
python src/run_regime_hmm.py --retrain-hmm
python src/run_hazard_train.py
python src/run_exposure.py
python src/run_onchain_features.py
```

This will:
- generate descriptive features
- train HMM model
- train hazard model
- compute exposure
- generate all outputs in `../out`

---

## Active BTC pipeline

### Daily run (apply existing models)

Use this for normal daily updates. This does **not retrain models**.

```bash
source .venv/bin/activate

python src/crawler/query.py
python src/run_onchain_features.py
python src/run_exposure.py

# python -m http.server 8000
# then open:
# http://localhost:8000/viewer/dashboard.html
```

Requirements:
- `../out/models/hmm_pack.joblib` must already exist
- `../out/models/hazard_pack.joblib` must already exist

---

### Refit / refresh models (periodic)

Use this when you want to retrain models on updated data.

```bash
source .venv/bin/activate

python src/crawler/query.py
python src/run_features.py
python src/run_regime_hmm.py --retrain-hmm
python src/run_hazard_train.py
python src/run_exposure.py
python src/run_onchain_features.py
```

Notes:
- HMM is retrained explicitly via `--retrain-hmm`
- Hazard is retrained every time `run_hazard_train.py` is executed
- Exposure is recomputed after model refresh

---

## Stage responsibilities

- `run_features.py`
  - builds descriptive BTC OHLCV features

- `run_regime_hmm.py`
  - fits/applies the HMM regime model
  - writes `../out/models/hmm_pack.joblib`

- `run_hazard_train.py`
  - trains calibrated hazard models
  - writes `../out/models/hazard_pack.joblib`

- `run_exposure.py`
  - applies HMM + hazard + exposure logic
  - writes the consolidated `../out/features.csv`

- `run_onchain_features.py`
  - builds descriptive on-chain features
  - writes `../out/onchain_features.csv`

---

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
