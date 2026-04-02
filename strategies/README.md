Active workflow:

- build SAFE features:
  `PYTHONPATH=statistics python statistics/src/run_exposure.py --hmm-mode filter --exposure-mode safe`
- derive candlestick research features from SAFE CSV:
  `python candles_btc_features.py --input ../statistics/out/features.csv --input-fmt csv --output out.csv`
- run interval research with the maintained tool:
  `python candlestick_research_tool_v4.py --input out.csv --key-col date --start 2026-03-13 --end 2026-03-13 --standardize --metric euclidean --min-sim 0.50 --out-dir research_out_v4`

Only `candles_btc_features.py` and `candlestick_research_tool_v4.py` are current. Older versioned research scripts were removed.
