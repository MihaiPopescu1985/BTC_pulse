# SAFE v4.0 Reproducibility

## Inputs
- `statistics/out/features.csv`
- `statistics/out/states.csv`
- `statistics/out/targets.csv`
- `statistics/data/daily_price.json`

## Core date range
- `2017-08-17` -> `2026-04-02`

## Walk-forward decision layer
Command:
```bash
PYTHONPATH=statistics python statistics/src/walkforward/run_decision_analysis_walkforward.py
```

Outputs:
- `statistics/out/decision_analysis_walkforward.csv`
- `statistics/out/decision_analysis_walkforward.md`

Accepted summary:
- total rows: `3151`
- usable rows: `2886`
- first usable date: `2018-02-04`

## Walk-forward policy proof
Command:
```bash
PYTHONPATH=statistics python statistics/src/walkforward/run_policy_backtest_walkforward.py
```

Outputs:
- `statistics/out/policy_backtest_walkforward.csv`
- `statistics/out/policy_backtest_walkforward.md`

## Walk-forward refinement / ablation
Command:
```bash
PYTHONPATH=statistics python statistics/src/walkforward/run_policy_refinement_walkforward.py
```

Outputs:
- `statistics/out/policy_refinement_walkforward.csv`
- `statistics/out/policy_refinement_walkforward.md`

Accepted summary:
- policy variants tested: `42`
- strongest Sharpe variant: `opp_only_lb6_ub7`

## Walk-forward stress testing
Command:
```bash
PYTHONPATH=statistics python statistics/src/walkforward/run_policy_stress_walkforward.py
```

Outputs:
- `statistics/out/policy_stress_walkforward.csv`
- `statistics/out/policy_stress_walkforward.md`

Accepted summary:
- explicit scenarios tested: `14`
- strongest median-Sharpe policy: `opp_only_lb6_ub7`
- strongest active drawdown-resilience policy: `defensive_trend_following_baseline`

## Execution assumptions
- BTC-only
- long/flat only
- signal formed on day `t`
- applied to day `t+1` close-to-close return
- default transaction cost: `10` bps per position change
- no intraday execution model

## Notes
- This reproducibility note documents the accepted SAFE v4.0 walk-forward branch only.
- Productive signal-generation scripts now live under `statistics/src/core`.
- The accepted validation branch now lives under `statistics/src/walkforward`.
- Descriptive and exploratory v4 iteration scripts now live under `statistics/src/research/v4_iteration`.
- It is a record of the frozen pipeline state, not a suggestion to rerun or extend experiments.
