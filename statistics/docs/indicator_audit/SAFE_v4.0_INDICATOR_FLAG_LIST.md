# SAFE v4.0 Indicator Flag List

This file is a cumulative caution list, not a delete list.

Purpose:

- track indicators that appear empty, misleading, or too overlapping to trust at face value
- preserve audit findings across family-by-family passes
- identify what should be challenged later in the final productive cleanup cycle

## redundant_alias

### Trend family

- `RVR_20`
  - empirically redundant with `TS_20`
  - same reliability profile on the tested trend-family targets
- `RVR_50`
  - empirically redundant with `TS_50`
  - same profile to numerical tolerance
- `RVR_200`
  - empirically redundant with `TS_200`
  - same reliability profile on the tested trend-family targets

## suspect_or_misleading

None currently flagged at repository level.

Reason:

- no indicator has yet been shown to be actively misleading enough to justify that label with confidence

## challenge_later

### Volatility family

- `parkinson_vol`
  - strong indicator, but very close to `garman_klass_vol`
  - should be challenged as part of the range-volatility pair
- `garman_klass_vol`
  - theoretically richer than `parkinson_vol`
  - empirically not clearly differentiated in the current evidence

### Position / mean-reversion family

- `time_since_local_high`
  - interpretable, but weak as a standalone signal
  - should survive only if later interaction tests justify it
- `time_since_local_low`
  - slightly better than `time_since_local_high`, but still weak standalone
  - should be challenged later as a contextual proxy rather than a core feature

### Participation family

- `volume_log1p`
  - descriptive, but weaker than normalized participation features
  - may reflect long-run market scale more than actionable local participation
  - should be challenged later against `relative_volume_20` and `volume_z`

### Regime / hazard family

- `HMM_DOM`
  - latent-state index is pack-internal and not stable semantic evidence
  - should be treated as diagnostic unless a later pass proves otherwise
- `P_DRIFT_HMM`
  - semantically valid, but weaker than `P_SHOCK_HMM`, `P_SURGE_HMM`, and the calibrated hazard outputs
  - should be challenged later before being treated as meaningful front-line context

### On-chain family

- `ONCHAIN_AMOUNT_PCT`
  - raw day-over-day flow change is much weaker than the normalized on-chain anomaly features
  - should be challenged later before being treated as meaningful context
- `ONCHAIN_WHALE_TX_PCT`
  - weakest active on-chain feature in the current evidence
  - should survive only if later interaction tests justify it
- `ONCHAIN_DOM_PCT`
  - noisy raw derivative of on-chain dominance
  - should be challenged later against `ONCHAIN_DOM_Z`

### General note

“challenge later” means:

- verify whether the indicator adds distinct value in the final merged walk-forward design
- do not remove it solely on first-pass overlap evidence
