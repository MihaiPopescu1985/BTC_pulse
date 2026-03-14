# How To

## Prepare
`python -m venv .venv`

### Windows
`./.venv/Scripts/activate`

### Linux
`source ./.venv/bin/activate`
`pip install -r ./requirements.txt`

## Run

### The complete BTC pipeline

#### Daily run
```
source .venv/bin/activate
python src/crawler/query.py
python src/run_onchain_features.py
python src/run_features.py     --asset btc --price-json data/daily_price.json
python src/run_hazard_train.py --asset btc --price-json data/daily_price.json
python src/run_regime_hmm.py   --asset btc --price-json data/daily_price.json
python src/run_exposure.py     --asset btc --price-json data/daily_price.json
python -m http.server 8000
# apoi:
# http://localhost:8000/viewer/dashboard.html
```

#### Once a month or once every three months
```
python src/crawler/query.py
python src/run_features.py        --asset btc --price-json data/daily_price.json
python src/run_hazard_train.py    --asset btc --price-json data/daily_price.json
python src/run_regime_hmm.py      --asset btc --price-json data/daily_price.json --hmm-mode filter
python src/run_exposure.py        --asset btc --price-json data/daily_price.json
python src/run_onchain_features.py --asset btc
python test/validate_features_contract.py --stage post
```

### The complete XAU pipeline
```
python src/run_features.py         --asset xau --price-json data/xau_daily_price.json
python src/run_hazard_train.py     --asset xau --price-json data/xau_daily_price.json
python src/run_regime_hmm.py       --asset xau --price-json data/xau_daily_price.json
python src/run_exposure.py         --asset xau --price-json data/xau_daily_price.json
python -m http.server 8000
# apoi
# http://localhost:8000/viewer/dashboard.html
```


python src/crawler/query.py

python src/util/print_features_range.py 2026-03-09 2026-03-12 --path out/btc/features.json >> daily_reading.txt
python src/util/print_features_range.py 2026-03-09 2026-03-12 --path out/btc/onchain_features.json >> daily_reading.txt
python src/util/safe_touch_probabilities.py   --price-json data/daily_price.json   --features-json out/btc/features.json   --date 2026-03-12 --days 10 --sims 20000 >> daily_reading.txt

python src/util/safe_narrator.py --asset btc --date 2026-02-05 --onchain-json out/btc/onchain_features.json
python src/util/safe_trade_context.py --show_thresholds
