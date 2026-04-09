# SAFE v4.0 Trend Reliability Report

## 1. Summary

- The active reliability script is [run_indicator_reliability.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/core/indicator_audit/run_indicator_reliability.py).
- It reads:
  - [features.csv](/home/mihai/Documents/BTC_pulse/statistics/out/features.csv)
  - [targets.csv](/home/mihai/Documents/BTC_pulse/statistics/out/targets.csv)
- It writes:
  - [indicator_reliability.csv](/home/mihai/Documents/BTC_pulse/statistics/out/indicator_audit/indicator_reliability.csv)
  - [indicator_reliability.md](/home/mihai/Documents/BTC_pulse/statistics/out/indicator_reliability.md)
- For the trend family, `ER_50` is the strongest empirical performer on upside-oriented 10-day outcomes.
- `TS_20`, `TS_50`, `TS_200`, and `ER_20` remain validated core trend descriptors.
- `LR_20` and `R_14` show meaningful secondary value and look useful for future walk-forward refinement.
- `R_7` is weaker than `R_14`, but still informative enough to keep as context.
- `RVR_*` is empirically redundant with `TS_*`, not just theoretically redundant.
- No broad pruning is justified from this report alone. The correct use is classification and better future signal design.

## 2. Ranking Table

Ranking inputs:

- correlation: Spearman against
  - `ret_10d`
  - `max_up_10d`
  - `max_down_10d`
  - `touch_up_2pct_10d`
  - `touch_down_2pct_10d`
- monotonicity score from the existing reliability buckets
- top-vs-bottom bucket separation from the existing reliability output

Aggregate columns below are simple descriptive composites built from the existing reliability metrics:

- `overall_rank_score`: average absolute trend-family evidence across the five targets
- `upside_rank_score`: average absolute evidence for `ret_10d`, `max_up_10d`, `touch_up_2pct_10d`
- `downside_rank_score`: average absolute evidence for `max_down_10d`, `touch_down_2pct_10d`

| Indicator | overall_rank_score | upside_rank_score | downside_rank_score | Initial class |
|---|---:|---:|---:|---|
| ER_50 | 0.330 | 0.124 | 0.025 | productive_core |
| TS_20 | 0.222 | 0.051 | 0.048 | productive_core |
| RVR_20 | 0.222 | 0.051 | 0.048 | redundant_alias |
| ER_20 | 0.208 | 0.070 | 0.019 | productive_core |
| LR_20 | 0.194 | 0.054 | 0.053 | productive_context |
| R_14 | 0.144 | 0.039 | 0.048 | productive_context |
| TS_50 | 0.119 | 0.051 | 0.022 | productive_core |
| RVR_50 | 0.119 | 0.051 | 0.022 | redundant_alias |
| LR_50 | 0.114 | 0.041 | 0.018 | research_context |
| ER_200 | 0.102 | 0.024 | 0.072 | research_context |
| LR_200 | 0.099 | 0.020 | 0.061 | research_context |
| TS_200 | 0.096 | 0.029 | 0.036 | productive_core |
| RVR_200 | 0.096 | 0.029 | 0.036 | redundant_alias |
| R_7 | 0.081 | 0.029 | 0.042 | productive_context |
| R_3 | 0.079 | 0.022 | 0.043 | research_context |

## 3. Per-Indicator Analysis

### R_3
- Weakest recent-return member overall.
- Some downside sensitivity, but the signal is noisy and inconsistent.
- Better treated as short-horizon context than as a direct ranking input.
- Classification: `research_context`

### R_7
- Modest but real signal.
- Better than `R_3`, weaker than `R_14`.
- Most useful as “recent swing” context rather than a core trend backbone.
- Classification: `productive_context`

### R_14
- Best recent-return member.
- Shows meaningful relation to `ret_10d`, `max_down_10d`, and `touch_down_2pct_10d`.
- Good candidate for “pullback versus already-extended move” logic.
- Classification: `productive_context`

### TS_20
- Strong short/medium opportunity relevance.
- Good monotonicity on `ret_10d`.
- Still one of the most useful live trend descriptors.
- Classification: `productive_core`

### TS_50
- Still important, but descriptively weaker than `ER_50` and somewhat weaker than `TS_20`.
- Remains central because it is already embedded in HMM, hazard, exposure, states, and walk-forward scoring.
- Classification: `productive_core`

### TS_200
- Lower headline strength, but useful as long-structure context.
- More contextual than tactical.
- Deserves to remain core because it frames the backdrop for time-sensitive opportunity signals.
- Classification: `productive_core`

### LR_20
- Best slope-family member.
- Stronger than `TS_20` on downside-oriented composite ranking, and competitive on upside relevance.
- Evidence supports it as a distinct contextual feature rather than a duplicate.
- Classification: `productive_context`

### LR_50
- Moderate evidence, weaker than `LR_20`.
- Useful as a comparator, but not yet strong enough to promote to core.
- Classification: `research_context`

### LR_200
- Mostly long-backdrop information.
- Better for structural interpretation than near-term opportunity ranking.
- Classification: `research_context`

### ER_20
- Strong and already productive.
- Not the strongest descriptively, but clearly useful and distinct.
- Best interpreted as path cleanliness confirmation.
- Classification: `productive_core`

### ER_50
- Clear empirical winner in the trend family.
- Strongest Spearman and strongest monotonicity on:
  - `ret_10d`
  - `max_up_10d`
  - `touch_up_2pct_10d`
- This is the strongest evidence-backed candidate for broader future walk-forward use.
- Classification: `productive_core`

### ER_200
- Limited upside value, better downside/context sensitivity.
- Useful as long-horizon cleanliness context, not a direct tactical driver.
- Classification: `research_context`

### RVR_20
- Empirically identical to `TS_20` for the targets tested.
- No added descriptive value beyond alias labeling.
- Classification: `redundant_alias`

### RVR_50
- Empirically the same as `TS_50` to numerical tolerance.
- No new signal contribution.
- Classification: `redundant_alias`

### RVR_200
- Empirically identical to `TS_200` for the targets tested.
- No new signal contribution.
- Classification: `redundant_alias`

## 4. Audit vs Evidence Comparison

### Does ER_50 outperform most trend indicators?
Yes.

Evidence:

- `ret_10d`: highest trend-family Spearman at about `0.136`
- `max_up_10d`: highest at about `0.188`
- `touch_up_2pct_10d`: highest at about `0.141`
- monotonicity is also the strongest and cleanest among the trend indicators on the main upside targets

Conclusion:

- The interpretive audit was correct to treat `ER_50` as one of the best future refinement candidates.

### Do R_7 / R_14 add meaningful signal?
Yes, but unevenly.

Evidence:

- `R_14` is clearly the stronger of the two.
- `R_14` has useful downside and short-swing sensitivity.
- `R_7` is weaker, but still informative enough to keep as context.

Conclusion:

- `R_14` is validated as a useful contextual indicator.
- `R_7` survives as secondary context, not as a core signal.

### Does LR_20 provide distinct value vs TS_20?
Yes.

Evidence:

- `LR_20` is materially weaker than `TS_20` on broad overall score, but still strong.
- It is competitive on upside relevance and stronger on downside-oriented composite ranking.
- It is not an alias. Its evidence profile is distinct enough to justify keeping it.

Conclusion:

- `LR_20` is a valid contextual comparator and a plausible future walk-forward refinement input.

### Are RVR_* truly redundant empirically?
Yes.

Evidence:

- `TS_20` vs `RVR_20`: same summary metrics across all tested targets
- `TS_200` vs `RVR_200`: same summary metrics across all tested targets
- `TS_50` vs `RVR_50`: same to numerical tolerance, with only negligible floating-point noise in one Spearman value

Conclusion:

- `RVR_*` should be treated as `redundant_alias`, not as distinct evidence.

## 5. Final Classification Table

| Indicator | Classification | Reason |
|---|---|---|
| R_3 | research_context | Too noisy to trust directly, but still useful as a very short impulse reference |
| R_7 | productive_context | Modest but real swing information |
| R_14 | productive_context | Best recent-return contextual feature |
| TS_20 | productive_core | Strong, stable short/medium trend backbone |
| TS_50 | productive_core | Central productive feature, structurally embedded |
| TS_200 | productive_core | Important long-structure backdrop |
| LR_20 | productive_context | Distinct shape/slope context with real evidence |
| LR_50 | research_context | Useful comparator, weaker operational evidence |
| LR_200 | research_context | Long-backdrop context only |
| ER_20 | productive_core | Distinct path-cleanliness core feature |
| ER_50 | productive_core | Strongest empirical trend-family indicator |
| ER_200 | research_context | Structural cleanliness context, not tactical core |
| RVR_20 | redundant_alias | No evidence beyond `TS_20` |
| RVR_50 | redundant_alias | No evidence beyond `TS_50` |
| RVR_200 | redundant_alias | No evidence beyond `TS_200` |

## 6. Next-Step Recommendations For Walk-Forward

- Keep the current trend backbone intact:
  - `TS_20`
  - `TS_50`
  - `TS_200`
  - `ER_20`
- Promote `ER_50` to the front of the next walk-forward refinement queue.
- Test `LR_20` as a confirmation / divergence layer rather than as a replacement for `TS_20`.
- Use `R_14` and then `R_7` to improve “fresh pullback versus already-extended move” context.
- Treat `RVR_*` as aliases in future analysis unless their implementation is intentionally differentiated.
- Do not use `R_3` as a primary ranking signal. If used, use it only as fast context around a stronger trend state.

## Bottom Line

- The audit’s central claim holds up.
- `ER_50` is the strongest underused trend indicator.
- `LR_20` and `R_14` are credible contextual additions for future walk-forward refinement.
- `RVR_*` is redundant in a literal empirical sense.
- The trend family should be preserved, but future walk-forward iterations should use it more selectively and more relationally.
