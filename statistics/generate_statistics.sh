#!/bin/bash

python src/run_onchain_features.py
python src/run_features.py     --asset btc --price-json data/daily_price.json
python src/run_hazard_train.py --asset btc --price-json data/daily_price.json
python src/run_regime_hmm.py   --asset btc --price-json data/daily_price.json
python src/run_exposure.py     --asset btc --price-json data/daily_price.json
