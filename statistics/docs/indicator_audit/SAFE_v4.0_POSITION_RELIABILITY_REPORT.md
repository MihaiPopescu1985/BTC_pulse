# SAFE v4.0 Position / Mean-Reversion Reliability Report

## 1. Summary

- The active reliability script remains [run_indicator_reliability.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/core/indicator_audit/run_indicator_reliability.py).
- It uses:
  - [features.csv](/home/mihai/Documents/BTC_pulse/statistics/out/features.csv)
  - [targets.csv](/home/mihai/Documents/BTC_pulse/statistics/out/targets.csv)
- For the position / mean-reversion family:
  - `band_w` is the strongest empirical indicator by a wide margin
  - `dist_from_mean_vol_units` is the best true mean-reversion-style indicator
  - `band_pos` is useful, but modest as a standalone predictor
  - `time_since_local_high` and `time_since_local_low` are weak standalone signals
- This family appears more useful for describing structural setup and timing context than for raw directional prediction alone.

## 2. Method

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

Composite ranking aids:

- `overall_rank_score`
- `upside_rank_score`
- `downside_rank_score`

These are descriptive ranking composites derived from the existing reliability output.

## 3. Indicator Ranking Table

| Indicator | overall_rank_score | upside_rank_score | downside_rank_score | Initial class |
|---|---:|---:|---:|---|
| band_w | 0.307 | 0.104 | 0.147 | productive_core |
| dist_from_mean_vol_units | 0.208 | 0.054 | 0.054 | productive_context |
| band_pos | 0.139 | 0.028 | 0.030 | productive_core |
| time_since_local_low | 0.138 | 0.025 | 0.016 | research_context |
| time_since_local_high | 0.098 | 0.026 | 0.006 | research_context |

## 4. Per-Indicator Analysis

### band_w
- Strongest indicator in this family on every ranking composite.
- Best on:
  - `max_up_10d`
  - `max_down_10d`
  - `touch_up_2pct_10d`
  - `touch_down_2pct_10d`
- This does not mean it is a directional predictor.
- It means structure width is highly informative about whether future excursions are likely to occur.
- Role:
  - structural expansion / compression context

### dist_from_mean_vol_units
- Best true mean-reversion feature in the family.
- Best on `ret_10d` among these indicators.
- Also materially useful on downside and upside touch context.
- Role:
  - stretch / pullback / equilibrium-distance context

### band_pos
- Useful but weaker than `band_w` and `dist_from_mean_vol_units`.
- Good as a direct location descriptor, but modest as a standalone signal.
- Most likely useful in interaction:
  - lower band + supportive trend
  - upper band + noisy trend
- Role:
  - direct envelope-location descriptor

### time_since_local_low
- Slightly stronger than `time_since_local_high`, but still weak.
- Better treated as descriptive path context than as a core decision input.
- Role:
  - local-bottom recency context

### time_since_local_high
- Weakest indicator in the family.
- Still interpretable, but low standalone evidence.
- Role:
  - local-top recency context

## 5. Audit vs Evidence Comparison

### Which indicators capture pullback vs extension best?

Best answer:

- `dist_from_mean_vol_units`
- then `band_pos`

Interpretation:

- `dist_from_mean_vol_units` is the better normalized stretch / equilibrium-distance signal
- `band_pos` is the better simple envelope-location signal

### Which distinguish overbought vs trending?

Best answer:

- `band_pos` by definition
- but `band_pos` alone is not strong enough to separate “overbought” from “healthy trend”
- this is likely an interaction problem:
  - `band_pos` needs trend and cleanliness context

### Which help entry timing vs just describing state?

Best candidates:

- `dist_from_mean_vol_units`
- `band_pos`

`band_w` is very informative, but mostly as a setup descriptor:

- wide structure
- compressed structure
- likely excursion environment

That is more “state” than “entry timing.”

### Which fail to provide useful signal?

Weakest standalone signals:

- `time_since_local_high`
- `time_since_local_low`

They do not fail completely, but they do not show strong enough standalone evidence to justify front-line use.

## 6. Final Classification Table

| Indicator | Classification | Reason |
|---|---|---|
| band_pos | productive_core | Most direct and interpretable envelope-location feature |
| band_w | productive_core | Strongest empirical family member; structural width matters |
| dist_from_mean_vol_units | productive_context | Best normalized stretch / pullback feature |
| time_since_local_high | research_context | Interpretable but weak standalone evidence |
| time_since_local_low | research_context | Slightly better than high-side twin, but still weak standalone |

## 7. Clear Next-Step Recommendations For Walk-Forward

- Keep `band_pos` as the direct structure-location anchor.
- Keep `band_w` prominent for setup context:
  - compressed vs already-wide structures
  - excursion-likely vs quiet states
- Promote `dist_from_mean_vol_units` as the best future test candidate for mean-reversion / pullback logic.
- Do not use `time_since_local_high` or `time_since_local_low` as core standalone ranking inputs yet.
- Test the family relationally later:
  - low `band_pos` + supportive trend
  - high `band_pos` + weak cleanliness
  - stretched `dist_from_mean_vol_units` inside constructive or weak structure

## Bottom Line

- `band_w` is the empirical winner in this family, but it is more structural-width than pure position.
- `dist_from_mean_vol_units` is the best true mean-reversion feature.
- `band_pos` remains the clearest interpretable location anchor, even though its standalone signal is modest.
- The time-since-extreme features are still descriptive, but not yet strong enough to promote.
