# SAFE v4.0 Volatility Reliability Report

## 1. Summary

- The active reliability script is [run_indicator_reliability.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/core/indicator_audit/run_indicator_reliability.py).
- It reads:
  - [features.csv](/home/mihai/Documents/BTC_pulse/statistics/out/features.csv)
  - [targets.csv](/home/mihai/Documents/BTC_pulse/statistics/out/targets.csv)
- It writes:
  - [indicator_reliability.csv](/home/mihai/Documents/BTC_pulse/statistics/out/indicator_audit/indicator_reliability.csv)
  - [indicator_reliability.md](/home/mihai/Documents/BTC_pulse/statistics/out/indicator_reliability.md)
- The volatility family is weak for raw `ret_10d`, but materially stronger for:
  - `max_up_10d`
  - `max_down_10d`
  - `touch_up_2pct_10d`
  - `touch_down_2pct_10d`
- `atr_pct` is the strongest downside-risk volatility indicator.
- `ewma_vol` is the strongest all-around upside-touch / excursion volatility indicator.
- `upside_semi_vol` is the best upside-leaning directional volatility feature.
- `parkinson_vol` and `garman_klass_vol` are strong range-volatility descriptors, but empirically very close to one another.

## 2. Method

The ranking uses the existing reliability output only.

Targets used:

- `ret_10d`
- `max_up_10d`
- `max_down_10d`
- `touch_up_2pct_10d`
- `touch_down_2pct_10d`

Metrics used:

- Spearman correlation
- monotonicity score
- top-vs-bottom bucket separation

Simple descriptive composites:

- `overall_rank_score`
  - average absolute evidence across the five targets
- `upside_rank_score`
  - average absolute evidence across `ret_10d`, `max_up_10d`, `touch_up_2pct_10d`
- `downside_rank_score`
  - average absolute evidence across `max_down_10d`, `touch_down_2pct_10d`

These are ranking aids, not model scores.

## 3. Indicator Ranking Table

| Indicator | overall_rank_score | upside_rank_score | downside_rank_score | Initial class |
|---|---:|---:|---:|---|
| atr_pct | 0.351 | 0.091 | 0.232 | productive_core |
| vol_20 | 0.350 | 0.102 | 0.187 | productive_core |
| ewma_vol | 0.346 | 0.100 | 0.210 | productive_core |
| upside_semi_vol | 0.323 | 0.110 | 0.138 | productive_context |
| parkinson_vol | 0.312 | 0.110 | 0.197 | research_context |
| garman_klass_vol | 0.306 | 0.108 | 0.196 | research_context |
| downside_semi_vol | 0.269 | 0.054 | 0.183 | productive_context |

## 4. Per-Indicator Analysis

### vol_20
- Best simple baseline realized-volatility feature.
- Not very useful for raw `ret_10d`, but clearly useful for future excursion and touch outcomes.
- Good monotonicity on downside and upside touch behavior.
- Role:
  - broad volatility backdrop

### atr_pct
- Strongest downside-risk volatility indicator.
- Best family member on:
  - `max_down_10d`
  - `touch_down_2pct_10d`
- Also useful for upside touch / excursion, but the main edge is downside movement scale.
- Role:
  - practical risk / movement-scale descriptor

### parkinson_vol
- Strong range-volatility signal.
- Very good on excursion and touch outcomes.
- Conceptually useful, but the main question is whether it adds anything beyond `garman_klass_vol` or `atr_pct`.
- Role:
  - research comparator for range-based volatility

### garman_klass_vol
- Nearly the same empirical story as `parkinson_vol`.
- Strong reliability on excursion / touch targets, but little distinctiveness.
- Role:
  - research comparator, not front-line core feature yet

### ewma_vol
- Best overall upside-sensitive broad volatility feature.
- Strong on:
  - `max_up_10d`
  - `touch_up_2pct_10d`
- Also strong on downside excursion and touch outcomes.
- Role:
  - fast volatility-regime change signal

### upside_semi_vol
- Strongest directional upside-context volatility feature.
- Best upside composite in this family.
- Evidence supports using it for “upside expansion vs generic stress” interpretation.
- Role:
  - productive directional context

### downside_semi_vol
- Better for downside than upside, but weaker than `atr_pct`.
- Still useful because it carries directional meaning rather than only total volatility.
- Likely more useful in interaction with trend / hazard than alone.
- Role:
  - productive directional context

## 5. Audit vs Evidence Comparison

### Which volatility indicators are strongest for upside opportunity context?

Top upside ranking:

1. `upside_semi_vol`
2. `parkinson_vol`
3. `garman_klass_vol`
4. `vol_20`
5. `ewma_vol`
6. `atr_pct`

Interpretation:

- `upside_semi_vol` is the cleanest directional upside context feature.
- `ewma_vol`, `vol_20`, `atr_pct`, `parkinson_vol`, and `garman_klass_vol` are all useful, but they are mostly describing “more movement coming” rather than “good upside specifically.”

### Which are strongest for downside risk context?

Top downside ranking:

1. `atr_pct`
2. `ewma_vol`
3. `parkinson_vol`
4. `garman_klass_vol`
5. `vol_20`
6. `downside_semi_vol`

Interpretation:

- `atr_pct` is the clearest practical downside-risk context feature.
- `ewma_vol` also matters, especially when recent volatility has accelerated.

### Which are best as structural volatility backdrop rather than tactical filters?

- `vol_20`
- `atr_pct`
- `ewma_vol`

These are the best candidates for stable volatility-state description.

### Are any volatility indicators empirically redundant with each other?

Yes, but less cleanly than the `TS_*` / `RVR_*` trend alias case.

Strongest candidate pair:

- `parkinson_vol`
- `garman_klass_vol`

Evidence:

- Pearson correlation about `0.995`
- nearly identical reliability profile across the tested targets

Conclusion:

- they are not yet proven literal aliases
- but they are close enough to be challenged later as a pair

### Are any indicators theoretically distinct but empirically weak?

Not weak enough to discard, but:

- `downside_semi_vol` is directionally meaningful while still weaker than `atr_pct` as a raw downside-risk descriptor
- `garman_klass_vol` is theoretically richer than `parkinson_vol`, yet empirically not clearly better

### Are any indicators likely useful mainly in interaction with other families?

Yes.

- `upside_semi_vol`
- `downside_semi_vol`

These look more useful as conditional context with trend / hazard / state information than as standalone scalars.

## 6. Final Classification Table

| Indicator | Classification | Reason |
|---|---|---|
| vol_20 | productive_core | Best simple realized-volatility backbone |
| atr_pct | productive_core | Strongest downside movement-scale descriptor |
| ewma_vol | productive_core | Best fast volatility-regime change descriptor |
| upside_semi_vol | productive_context | Best directional upside-volatility context |
| downside_semi_vol | productive_context | Useful directional downside-stress context |
| parkinson_vol | research_context | Strong range-volatility comparator, but not clearly essential |
| garman_klass_vol | research_context | Theoretically richer, empirically too close to Parkinson to promote yet |

## 7. Clear Next-Step Recommendations For Walk-Forward

- Keep broad volatility backdrop centered on:
  - `vol_20`
  - `atr_pct`
  - `ewma_vol`
- Use `upside_semi_vol` to distinguish upside expansion from generic high-volatility stress.
- Use `downside_semi_vol` only in combination with trend or hazard context, not as a standalone filter.
- Challenge `parkinson_vol` and `garman_klass_vol` together later. They may be too close to both survive as distinct productive volatility features.

## Bottom Line

- The volatility family is clearly useful, but mostly for excursion and touch behavior rather than raw forward return.
- `atr_pct`, `vol_20`, and `ewma_vol` are the strongest core volatility descriptors.
- `upside_semi_vol` is the most interesting underused directional volatility feature.
- `parkinson_vol` and `garman_klass_vol` should remain available for now, but they belong on the challenge list.
