# SAFE v4.0 Regime / Hazard Reliability Report

## 1. Summary

- The regime / hazard family is materially stronger than the raw participation family and behaves like genuine decision-layer context.
- The strongest empirical members are:
  - `P_CORE_HMM`
  - `P_CORRECTION_10D_CAL`
  - `P_REBOUND_10D_CAL`
- `P_SHOCK_HMM` is also clearly useful, especially on downside-oriented outcomes.
- `P_SURGE_HMM` is a useful positive-context regime feature.
- `HMM_CONF` is modestly useful as confidence context.
- `HMM_DOM` has low direct value and should be treated as diagnostic.

Important interpretation rule:

- strong reliability here does **not** mean these are independent upstream features
- these are already-compressed model outputs
- they are useful as decision-layer context, not fresh evidence sources

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
| P_CORE_HMM | 0.334 | 0.116 | 0.122 | productive_context |
| P_CORRECTION_10D_CAL | 0.331 | 0.080 | 0.214 | productive_core |
| P_REBOUND_10D_CAL | 0.319 | 0.115 | 0.113 | productive_core |
| P_SURGE_HMM | 0.237 | 0.067 | 0.067 | productive_context |
| P_SHOCK_HMM | 0.212 | 0.048 | 0.132 | productive_core |
| HMM_DOM | 0.144 | 0.030 | 0.037 | diagnostic_only |
| HMM_CONF | 0.131 | 0.067 | 0.017 | productive_context |
| P_DRIFT_HMM | 0.110 | 0.042 | 0.022 | research_context |

## 4. Per-Indicator Analysis

### P_CORE_HMM
- Strongest overall composite in this family.
- Interpreted correctly, this does not mean “core is bullish.”
- It means the neutral/non-extreme regime assignment itself carries real state information.
- Best used as contextual regime character, not as a direct trigger.

### P_CORRECTION_10D_CAL
- Strongest downside ranking feature in the family.
- Best on:
  - `max_down_10d`
  - `touch_down_2pct_10d`
- Clearly useful as risk ranking context.
- This is one of the most decision-relevant model-derived outputs in SAFE.

### P_REBOUND_10D_CAL
- Strongest upside-ranking hazard output.
- Best on:
  - `max_up_10d`
  - upside-oriented forward outcomes
- Clearly useful as opportunity-ranking context.

### P_SURGE_HMM
- Best positive semantic regime feature.
- Useful for upside context, but weaker than the calibrated rebound hazard.
- Better treated as regime flavor than as the main ranking scalar.

### P_SHOCK_HMM
- Strong downside-context semantic regime feature.
- Stronger on downside than upside, as expected.
- Useful as a stress-state input.

### HMM_CONF
- Moderate value.
- Strongest use is confidence modulation rather than directional ranking.
- Evidence does not support treating it as a main signal, but it does support keeping it as context.

### HMM_DOM
- Weakest meaningful feature in the family.
- Some empirical relation exists, but the field is still pack-internal and latent-state-index based.
- That makes it a poor front-line decision feature even if it shows some surface-level reliability.

### P_DRIFT_HMM
- Weakest semantic regime probability in this family.
- Not empty, but clearly less useful than `P_SHOCK_HMM`, `P_SURGE_HMM`, or the hazard outputs.
- Better kept as contextual or interpretive support.

## 5. Audit vs Evidence Comparison

### Which regime indicators are most useful as tradable market-state context?

Best answer:

- `P_SHOCK_HMM`
- `P_SURGE_HMM`
- `P_CORE_HMM`

Interpretation:

- `P_SHOCK_HMM` is the clearest stress-state regime feature
- `P_SURGE_HMM` is the clearest positive expansion regime feature
- `P_CORE_HMM` is useful as neutral-state context

`P_DRIFT_HMM` looks materially weaker than the others.

### Which hazard indicators are most useful as opportunity / risk ranking context?

Best answer:

- `P_CORRECTION_10D_CAL`
- `P_REBOUND_10D_CAL`

Interpretation:

- both are clearly useful as ranking features
- they should continue to be treated as ranked context, not literal calibrated probabilities

### Which indicators are mostly diagnostic?

- `HMM_DOM`

It is not meaningless, but it is not a robust decision-layer feature because latent-state indexing is pack-specific and internal.

### Which are at greatest risk of circularity or double counting?

Highest caution:

- `P_CORRECTION_10D_CAL`
- `P_REBOUND_10D_CAL`
- all semantic HMM probabilities when combined naively with the raw features they were built from

Interpretation:

- these are useful outputs
- but they are not independent evidence sources

### Are P_CORRECTION_10D_CAL and P_REBOUND_10D_CAL useful as ranking features, or too close to final decision outputs?

They are useful as ranking features.

They are already close to decision-layer objects, and that is acceptable.

The caution is:

- do not count them as fresh upstream evidence in later merged feature reasoning

### Are HMM_CONF and HMM_DOM useful inputs, or mainly interpretation aids?

- `HMM_CONF`:
  - useful as confidence modulation
  - not a main directional signal
- `HMM_DOM`:
  - mainly interpretation / diagnostic aid

## 6. Final Classification Table

| Indicator | Classification | Reason |
|---|---|---|
| P_SHOCK_HMM | productive_core | strongest semantic stress-state decision context |
| P_CORRECTION_10D_CAL | productive_core | strongest downside hazard ranking feature |
| P_REBOUND_10D_CAL | productive_core | strongest upside hazard ranking feature |
| P_CORE_HMM | productive_context | useful neutral-state context, but not a primary trigger |
| P_SURGE_HMM | productive_context | useful upside regime flavor / expansion context |
| HMM_CONF | productive_context | confidence modulation, not directional evidence |
| P_DRIFT_HMM | research_context | weaker semantic regime probability than the others |
| HMM_DOM | diagnostic_only | internal latent-state index, not robust front-line evidence |

## 7. Clear Next-Step Recommendations For Walk-Forward

- Keep `P_CORRECTION_10D_CAL` and `P_REBOUND_10D_CAL` in the decision layer as ranking features.
- Keep `P_SHOCK_HMM` as explicit downside/stress context.
- Use `P_SURGE_HMM` and `P_CORE_HMM` as secondary regime-context modifiers.
- Use `HMM_CONF` only as a trust / modulation feature.
- Do not treat `HMM_DOM` as an ordinary predictive feature.
- In later merged feature reasoning, count the regime / hazard family as compressed model context, not as independent raw evidence.

## Bottom Line

- The hazard outputs are clearly useful.
- `P_SHOCK_HMM` is the most useful direct semantic regime feature.
- `P_DRIFT_HMM` is the weakest semantic regime probability in this family.
- `HMM_DOM` should remain diagnostic.
- The main danger in this family is not weakness. It is double counting.
