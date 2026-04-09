# SAFE v4.0 Participation Reliability Report

## 1. Summary

- The active reliability script remains [run_indicator_reliability.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/core/indicator_audit/run_indicator_reliability.py).
- It evaluates the current feature store against [targets.csv](/home/mihai/Documents/BTC_pulse/statistics/out/targets.csv).
- In the participation family:
  - `volume_z` is the strongest empirical indicator
  - `relative_volume_20` is weaker empirically, but has cleaner operational meaning
  - `volume_log1p` is the weakest normalized signal and looks more descriptive than decision-oriented
- Participation adds some information, but not at the level of the stronger trend or volatility families.
- Its main value looks contextual:
  - confirmation
  - unusual activity detection
  - continuation quality vs weak moves

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

These are descriptive ranking composites built from the existing reliability output.

## 3. Indicator Ranking Table

| Indicator | overall_rank_score | upside_rank_score | downside_rank_score | Initial class |
|---|---:|---:|---:|---|
| volume_z | 0.308 | 0.054 | 0.075 | productive_context |
| relative_volume_20 | 0.206 | 0.034 | 0.042 | productive_core |
| volume_log1p | 0.177 | 0.039 | 0.045 | research_context |

## 4. Per-Indicator Analysis

### volume_z
- Strongest family member by all three ranking composites.
- Best on:
  - `ret_10d`
  - `max_up_10d`
  - `max_down_10d`
  - `touch_down_2pct_10d`
- Also respectable on `touch_up_2pct_10d`.
- Main caveat:
  - lower usable sample count than the other participation indicators because of the longer adaptive window.
- Role:
  - unusual participation detector

### relative_volume_20
- Weaker than `volume_z` empirically, but cleaner operationally.
- Best interpreted as local confirmation:
  - is current participation above recent normal?
- It does not dominate any one target, but it is directionally consistent.
- Role:
  - local participation confirmation

### volume_log1p
- Some descriptive relationship to outcomes, but weaker and less clean.
- Likely contaminated by long-run market growth and scale changes.
- Better as context than as a front-line decision signal.
- Role:
  - raw activity scale descriptor

## 5. Audit vs Evidence Comparison

### Does participation confirm trend strength?

Yes, modestly.

Evidence:

- both `relative_volume_20` and `volume_z` show positive relation to upside excursion / touch outcomes
- the family is not strong enough to carry the signal by itself
- it looks better as a confirmer than as a standalone driver

### Does it predict continuation vs failure?

Somewhat.

Best evidence:

- `volume_z` has the clearest relation to:
  - better upside excursion
  - worse downside excursion when participation is unusually intense

Interpretation:

- unusual participation appears to predict “more movement,” not necessarily only good movement
- this makes participation more useful when conditioned on trend / structure than in isolation

### Does it distinguish strong moves from weak moves?

Yes, especially `relative_volume_20`.

Interpretation:

- `relative_volume_20` is the cleanest feature for saying whether the move is happening on above-normal local participation
- `volume_z` adds the “unusual vs normal” dimension

### Does it add value beyond volatility?

Probably yes, but modestly and conditionally.

Interpretation:

- volatility says how much movement risk exists
- participation says how much market is involved
- the participation family looks most useful for:
  - confirming continuation
  - rejecting weak moves
  - identifying unusual bursts of involvement

## 6. Final Classification Table

| Indicator | Classification | Reason |
|---|---|---|
| relative_volume_20 | productive_core | Cleanest and most operational participation-confirmation feature |
| volume_z | productive_context | Strongest empirical signal, but longer-window and lower-sample |
| volume_log1p | research_context | More descriptive than decision-oriented; likely scale-contaminated |

## 7. Clear Next-Step Recommendations For Walk-Forward

- Use `relative_volume_20` as the default participation confirmation feature.
- Use `volume_z` to detect unusual activity bursts, especially when testing continuation vs failure logic.
- Do not rely on participation as a standalone source of edge.
- Use participation mainly in interaction with:
  - trend strength
  - rebound attempts
  - noisy vs clean continuation
- Treat `volume_log1p` as descriptive context unless later tests prove distinct value.

## Bottom Line

- Participation is useful, but not dominant.
- `relative_volume_20` is the cleanest practical participation feature.
- `volume_z` is the strongest empirical activity anomaly feature.
- `volume_log1p` should remain available, but it does not currently justify front-line use.
