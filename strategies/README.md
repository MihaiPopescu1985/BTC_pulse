Active workflow:

- build SAFE features (from the repository root):
  `.venv/bin/python statistics/src/core/run_exposure.py --hmm-mode filter --exposure-mode safe`
- derive candlestick research features from SAFE CSV:
  `python candles_btc_features.py --input ../statistics/out/features.csv --input-fmt csv --output out.csv`
- run interval research with the maintained tool:
  `python candlestick_research_tool_v4.py --input out.csv --key-col date --start 2026-11-18 --end 2026-11-22 --standardize --metric euclidean --min-sim 0.50 --out-dir research_out_v4`

`--start`/`--end` select the query window, so they must fall inside the range
`out.csv` covers; `--key-col` is `date` because `features.csv` names it that way.
The same two steps are wired up as the `Strategies - candles similarities`
button in `simple-runner.yml`.

Only `candles_btc_features.py` and `candlestick_research_tool_v4.py` are current. Older versioned research scripts were removed.
