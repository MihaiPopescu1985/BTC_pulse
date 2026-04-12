# SAFE v4.0 Buy-Side Hybrid Validation

## Purpose

- validate whether `hybrid_weighted_balanced` is stable enough to replace `baseline_fixed_weight` as the buy-side reference
- no new ideas, trade rules, execution logic, capital management, or backtesting are introduced

## Validation Dimensions

- parameter sensitivity: nearby fixed/exhaustion/ordinal weights around `0.40 / 0.30 / 0.30`
- time-split robustness: early, middle, and late thirds of the held-out test period
- regime robustness: high/low volatility, TS_50 positive/negative, and high/low shock probability subsets
- threshold stability: retained in the detailed CSV for standard score cutoffs
- validation setting counts: `full` `1`, `regime` `6`, `time_split` `3`

## Full-Test Reference

- fixed baseline avg / median best distance: `0.047` / `0.026`
- hybrid avg / median best distance: `0.035` / `0.025`
- fixed baseline best-pick within 5% / 3%: `0.733` / `0.578`
- hybrid best-pick within 5% / 3%: `0.822` / `0.667`
- fixed baseline top-decile 5% / 3%: `0.562` / `0.438`
- hybrid top-decile 5% / 3%: `0.667` / `0.500`

## Strongest Hybrid Settings

- `time_split` / `test_late_third`: distance delta `0.027`, 5% delta `0.188`, top10 5% delta `0.000`
- `regime` / `regime_high_shock`: distance delta `0.016`, 5% delta `0.114`, top10 5% delta `-0.083`
- `regime` / `regime_ts50_negative`: distance delta `0.016`, 5% delta `0.069`, top10 5% delta `0.074`
- `full` / `full_test`: distance delta `0.012`, 5% delta `0.089`, top10 5% delta `0.104`
- `regime` / `regime_high_vol`: distance delta `0.012`, 5% delta `0.069`, top10 5% delta `0.042`

## Weakest Hybrid Settings

- `regime` / `regime_low_shock`: distance delta `-0.001`, 5% delta `0.000`, top10 5% delta `0.042`
- `time_split` / `test_early_third`: distance delta `0.001`, 5% delta `0.000`, top10 5% delta `0.062`
- `regime` / `regime_ts50_positive`: distance delta `0.002`, 5% delta `0.038`, top10 5% delta `0.091`
- `time_split` / `test_middle_third`: distance delta `0.005`, 5% delta `0.062`, top10 5% delta `0.000`
- `regime` / `regime_low_vol`: distance delta `0.006`, 5% delta `0.080`, top10 5% delta `0.000`

## Decision

- recommendation: **Promote hybrid**
- Hybrid distance win rate across validation settings: `0.900`.
- Hybrid 5% best-pick non-loss rate: `1.000`.
- Hybrid 3% best-pick non-loss rate: `1.000`.
- Hybrid top-decile 5% non-loss rate: `0.900`.
- Core full/time/regime distance win rate: `0.900`.

## Interpretation

- promotion requires the hybrid to beat or tie the fixed baseline across more than the original split-level headline result
- if the hybrid wins distance but loses too often on zone/top-decile quality, it should remain a candidate rather than become the reference
- this is still a research timing-layer validation, not a trading-system proof
