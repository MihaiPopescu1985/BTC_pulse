# SAFE v4.0 On-Chain Reliability Report

## 1. Summary

- For on-chain, weak short-horizon direct prediction does not automatically mean low value.
- The strongest direct on-chain relations to 10-day forward price behavior come from the z-score-style indicators:
  - `ONCHAIN_VOL_Z`
  - `ONCHAIN_DOM_Z`
  - `ONCHAIN_WHALE_SHARE_Z`
- The raw percent-change fields are materially weaker.
- `ONCHAIN_DOM_Z` is the strongest upside-context on-chain feature.
- `ONCHAIN_WHALE_SHARE_Z` is the strongest downside-structural on-chain feature.
- `ONCHAIN_VOL_Z` is the most balanced broad on-chain context feature.

## 2. Method

To preserve the existing reliability workflow, the same script was reused with:

- features input:
  - [onchain_features.csv](/home/mihai/Documents/BTC_pulse/statistics/out/onchain_features.csv)
- targets input:
  - [targets.csv](/home/mihai/Documents/BTC_pulse/statistics/out/targets.csv)

Generated outputs:

- [onchain_indicator_reliability.csv](/home/mihai/Documents/BTC_pulse/statistics/out/indicator_audit/onchain_indicator_reliability.csv)
- [onchain_indicator_reliability.md](/home/mihai/Documents/BTC_pulse/statistics/out/onchain_indicator_reliability.md)

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

These are descriptive ranking composites, not model scores.

## 3. Indicator Ranking Table

| Indicator | overall_rank_score | upside_rank_score | downside_rank_score | Initial class |
|---|---:|---:|---:|---|
| ONCHAIN_VOL_Z | 0.246 | 0.039 | 0.024 | productive_context |
| ONCHAIN_DOM_Z | 0.240 | 0.059 | 0.068 | productive_context |
| ONCHAIN_WHALE_SHARE_Z | 0.189 | 0.021 | 0.094 | productive_context |
| ONCHAIN_DOM_PCT | 0.081 | 0.004 | 0.012 | challenge_later |
| ONCHAIN_AMOUNT_PCT | 0.074 | 0.009 | 0.008 | challenge_later |
| ONCHAIN_WHALE_TX_PCT | 0.032 | 0.005 | 0.014 | challenge_later |

## 4. Per-Indicator Analysis

### ONCHAIN_VOL_Z
- Best broad on-chain context feature by overall score.
- Modest direct predictive strength, but consistent.
- Best interpreted as unusual total flow intensity, not as a tactical trigger.

### ONCHAIN_DOM_Z
- Strongest upside-context on-chain indicator.
- Best on:
  - `max_up_10d`
  - `touch_up_2pct_10d`
- Best interpreted as structural dominance shift rather than immediate entry timing.

### ONCHAIN_WHALE_SHARE_Z
- Strongest downside-context on-chain indicator.
- Best on:
  - `max_down_10d`
  - `touch_down_2pct_10d`
- Best interpreted as structural risk / concentration context.

### ONCHAIN_AMOUNT_PCT
- Weak.
- Day-over-day amount change looks too noisy to carry much useful signal by itself.

### ONCHAIN_WHALE_TX_PCT
- Weakest production-facing on-chain feature.
- Conceptually interesting, but current evidence is too small and noisy.

### ONCHAIN_DOM_PCT
- Slightly better than whale-tx percent change, but still weak.
- Looks more like a noisy short-horizon derivative than a stable useful context feature.

## 5. Audit vs Evidence Comparison

### Which on-chain indicators have the strongest direct relation to forward price behavior?

Best direct relations:

- `ONCHAIN_DOM_Z`
- `ONCHAIN_VOL_Z`
- `ONCHAIN_WHALE_SHARE_Z`

These are still only modest in absolute short-horizon predictive power, but clearly stronger than the raw percentage-change features.

### Which look more like structural / regime context than direct predictive features?

Most clearly structural:

- `ONCHAIN_VOL_Z`
- `ONCHAIN_DOM_Z`
- `ONCHAIN_WHALE_SHARE_Z`

Interpretation:

- these seem better suited to background state conditioning than to stand-alone short-term signals

### Which indicators look most likely to help later when combined with trend / volatility / participation?

Most promising interaction candidates:

- `ONCHAIN_DOM_Z`
  - with trend or positive regime context
- `ONCHAIN_WHALE_SHARE_Z`
  - with downside risk / shock context
- `ONCHAIN_VOL_Z`
  - with volatility-expansion or participation-confirmation logic

### Do whale-related indicators tell a distinct story from total-activity indicators?

Yes.

- `ONCHAIN_VOL_Z` captures broad flow intensity
- `ONCHAIN_WHALE_SHARE_Z` captures concentration / whale-share structure
- `ONCHAIN_DOM_Z` captures large-actor dominance versus smaller activity

These are related, but not empty overlap.

### Do z-score-style on-chain indicators look more useful than raw percentage-change indicators?

Yes, clearly.

This is the strongest family-level conclusion from the evidence.

### Are any on-chain indicators clearly too noisy or empty to trust at face value?

Yes, the weakest group is:

- `ONCHAIN_WHALE_TX_PCT`
- `ONCHAIN_DOM_PCT`
- `ONCHAIN_AMOUNT_PCT`

They are not necessarily useless, but they are too weak to trust without later interaction testing.

## 6. Final Classification Table

| Indicator | Classification | Reason |
|---|---|---|
| ONCHAIN_VOL_Z | productive_context | best broad on-chain activity anomaly context |
| ONCHAIN_DOM_Z | productive_context | strongest upside-structural on-chain feature |
| ONCHAIN_WHALE_SHARE_Z | productive_context | strongest downside-structural on-chain feature |
| ONCHAIN_AMOUNT_PCT | challenge_later | too noisy as a short-horizon raw flow-change feature |
| ONCHAIN_WHALE_TX_PCT | challenge_later | weakest active on-chain feature |
| ONCHAIN_DOM_PCT | challenge_later | noisy raw derivative of dominance |

## 7. Clear Next-Step Recommendations

- Keep the z-score-style on-chain indicators as the active on-chain context layer.
- Do not promote any on-chain feature to `productive_core` yet.
- Treat on-chain as structural context, not tactical entry timing.
- Challenge the raw percent-change fields later rather than removing them now.
- Most promising later interactions:
  - `ONCHAIN_DOM_Z` with trend / regime strength
  - `ONCHAIN_WHALE_SHARE_Z` with downside stress context
  - `ONCHAIN_VOL_Z` with volatility / participation expansion logic

## Bottom Line

- On-chain does add information, but mostly as structural context.
- The z-score-style on-chain indicators are the only clearly worthwhile front-line members of this family at this stage.
- The raw percent-change on-chain fields should be treated cautiously and challenged later, not trusted at face value.
