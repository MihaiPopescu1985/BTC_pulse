# SAFE v4.0 Interaction Discovery

This note moves from single-indicator validation to fixed-template interaction testing.

Scope:

- inputs:
  - [features.csv](/home/mihai/Documents/BTC_pulse/statistics/out/features.csv)
  - [onchain_features.csv](/home/mihai/Documents/BTC_pulse/statistics/out/onchain_features.csv)
  - [targets.csv](/home/mihai/Documents/BTC_pulse/statistics/out/targets.csv)
- runner:
  - [run_interaction_discovery.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/core/interaction_discovery/run_interaction_discovery.py)
- full output table:
  - [interaction_discovery.csv](/home/mihai/Documents/BTC_pulse/statistics/out/interaction_discovery/interaction_discovery.csv)

Method:

- no model changes
- no feature engineering
- no optimization loop
- 15 fixed rule templates only
- templates use simple sign logic plus empirical median / quartile cutoffs from the live feature surface
- ranking scores are sample-weighted, with full weight reached at `n >= 75`
- `dist_from_mean` in this repository is `dist_from_mean_vol_units`
- `range_score` is not an active exported field, so this pass uses `band_w` as the structural-width proxy

Threshold frame used in this run:

- `ER_50`: median `0.1593`, 75th percentile `0.2698`
- `ER_20`: 75th percentile `0.3741`
- `dist_from_mean_vol_units`: median `0.0450`, 75th percentile `0.5497`
- `band_w`: 25th percentile `0.3705`, 75th percentile `0.6934`
- `relative_volume_20`: median `0.9385`, 75th percentile `1.2269`
- `volume_z`: median `-0.1657`, 75th percentile `0.7681`
- `P_CORRECTION_10D_CAL`: median `0.1862`, 25th percentile `0.1472`
- `P_REBOUND_10D_CAL`: 75th percentile `0.2043`
- `P_SHOCK_HMM`: median `0.0002`, 90th percentile `0.9891`
- `P_CORE_HMM`: median `0.0004`, 75th percentile `0.9479`
- `ONCHAIN_DOM_Z`: median `-0.2633`, 75th percentile `0.5388`
- `ONCHAIN_VOL_Z`: 75th percentile `0.9018`
- `ONCHAIN_WHALE_SHARE_Z`: 75th percentile `0.2403`

Interpretation rule:

- highlight conditions with usable samples first
- treat tiny slices as hints only, not as decision-ready evidence
- compare each condition against the rest of the sample, not against an optimized benchmark

## Strong Upside Conditions

### `structural_onchain_tailwind`

- rule:
  - `TS_50 > 0`
  - `TS_200 > 0`
  - `ER_50 >= median`
  - `P_REBOUND_10D_CAL >= 75th percentile`
  - `ONCHAIN_DOM_Z >= 75th percentile`
  - `ONCHAIN_VOL_Z >= 75th percentile`
- sample size: `89`
- performance:
  - `ret_10d mean = 4.70%`
  - `max_up_10d mean = 14.54%`
  - `touch_up_2pct_10d = 85.39%`
  - separation vs rest:
    - `ret_10d = +3.24pp`
    - `max_up_10d = +5.73pp`
    - `touch_up_2pct_10d = +4.23pp`
- interpretation:
  - the best usable upside template is not trend-only
  - it needs supportive medium / long trend, rebound skew, and strong on-chain dominance / flow context
  - this looks like structural tailwind, not a pure tactical breakout signal

### `upside_probability_stack`

- rule:
  - `TS_50 > 0`
  - `TS_200 > 0`
  - `ER_50 >= 75th percentile`
  - `P_REBOUND_10D_CAL >= 75th percentile`
  - `P_SHOCK_HMM <= median`
  - `relative_volume_20 >= median`
  - `ONCHAIN_DOM_Z >= median`
- sample size: `85`
- performance:
  - `ret_10d mean = 5.16%`
  - `max_up_10d mean = 13.81%`
  - `touch_up_2pct_10d = 83.53%`
- interpretation:
  - the cleanest high-touch upside stack combines direction, cleanliness, rebound skew, participation, and on-chain support
  - it is a broad “constructive environment” condition rather than an entry-timing rule

### `expansion_with_participation`

- rule:
  - `TS_50 > 0`
  - `ER_50 >= 75th percentile`
  - `ewma_vol >= 75th percentile` or `atr_pct >= 75th percentile`
  - `relative_volume_20 >= 75th percentile` or `volume_z >= 75th percentile`
  - `P_SHOCK_HMM <= median`
- sample size: `49`
- performance:
  - `ret_10d mean = 11.48%`
  - `max_up_10d mean = 19.12%`
  - `touch_up_2pct_10d = 85.71%`
  - separation vs rest:
    - `ret_10d = +10.08pp`
    - `max_up_10d = +10.31pp`
- interpretation:
  - the strongest upside-excursion slice is trend plus expanding movement plus participation
  - this is the clearest “swing expansion” condition in the first interaction pass
  - caution: it is strongly two-sided, not a low-risk condition

### `squeeze_release_up`

- rule:
  - `TS_50 > 0`
  - `ER_50 >= 75th percentile`
  - `band_w <= 25th percentile`
  - `relative_volume_20 >= 75th percentile` or `volume_z >= 75th percentile`
  - `P_SHOCK_HMM <= median`
- sample size: `49`
- performance:
  - `ret_10d mean = 3.08%`
  - `touch_up_2pct_10d = 85.71%`
  - `touch_down_2pct_10d = 69.39%`
- interpretation:
  - compression plus improving participation does help upside touch odds
  - this is a better “movement release” condition than a pure directional edge

## Strong Downside-Risk Conditions

### `low_risk_base`

- rule:
  - `TS_200 > 0`
  - `P_CORRECTION_10D_CAL <= 25th percentile`
  - `P_SHOCK_HMM <= median`
  - `P_CORE_HMM >= 75th percentile`
- sample size: `209`
- performance:
  - `ret_10d mean = 2.07%`
  - `max_down_10d mean = -4.69%`
  - `touch_down_2pct_10d = 68.42%`
  - separation vs rest:
    - `max_down_10d = +3.44pp`
    - `touch_down_2pct_10d = -11.63pp`
- interpretation:
  - the broadest downside-avoidance condition is regime-led, not pullback-led
  - positive long backdrop plus low correction / shock context is more reliable than “buy the dip” by itself

### `squeeze_release_up`

- sample size: `49`
- downside profile:
  - `max_down_10d mean = -3.98%`
  - `touch_down_2pct_10d = 69.39%`
  - separation vs rest:
    - `max_down_10d = +3.98pp`
    - `touch_down_2pct_10d = -10.04pp`
- interpretation:
  - the best short-horizon downside control in this pass came from tight structure plus participation, not from raw hazard alone

### `downside_avoidance_stack`

- rule:
  - `TS_50 > 0`
  - `TS_200 > 0`
  - `P_CORE_HMM >= median`
  - `P_CORRECTION_10D_CAL <= 25th percentile`
  - `P_SHOCK_HMM <= median`
  - `ONCHAIN_DOM_Z >= median`
- sample size: `53`
- performance:
  - `touch_down_2pct_10d = 64.15%`
  - `max_down_10d mean = -5.75%`
- interpretation:
  - this is a sensible “safer constructive backdrop” condition
  - it helps on downside avoidance, but it is weaker than `low_risk_base`
  - on-chain dominance adds some support, but not a dramatic standalone improvement

## High-Probability Touch Conditions

### `upside_probability_stack`

- touch result:
  - `touch_up_2pct_10d = 83.53%`
- key point:
  - this is the clearest broad condition for a +2% touch within 10 days
  - it is more useful as a conditional environment than as a standalone trade trigger

### `structural_onchain_tailwind`

- touch result:
  - `touch_up_2pct_10d = 85.39%`
- key point:
  - on-chain strength matters most when trend and rebound context are already supportive

### `expansion_with_participation`

- touch result:
  - `touch_up_2pct_10d = 85.71%`
- caution:
  - `touch_down_2pct_10d = 91.84%`
- interpretation:
  - this is a high-movement condition, not a clean upside-only condition
  - useful for expected excursion, not for assuming downside is absent

### Tiny but notable slices

- `clean_breakout_continuation`
  - sample size: `5`
  - `touch_up_2pct_10d = 100%`
  - `touch_down_2pct_10d = 40%`
- `rebound_attempt_against_weak_backdrop`
  - sample size: `8`
  - `touch_up_2pct_10d = 100%`
  - `touch_down_2pct_10d = 87.5%`

These are interesting, but too small for decision use at this stage.

## Weak / Misleading Combinations

### `constructive_pullback`

- rule:
  - supportive medium / long trend
  - ER_50 at least median
  - mild pullback from mean
  - correction risk at or below median
  - shock risk low
- sample size: `8`
- performance:
  - `ret_10d mean = -0.52%`
  - `touch_down_2pct_10d = 87.5%`
- interpretation:
  - the naive “supportive trend plus mild pullback plus low shock” story did not produce a usable edge here
  - pullback context alone is not enough

### `low_risk_pullback`

- sample size: `72`
- performance:
  - `ret_10d mean = 0.02%`
  - `touch_down_2pct_10d = 86.11%`
- interpretation:
  - pullback without stronger cleanliness / participation / structural support is weak
  - this is a good example of a plausible narrative that does not survive basic conditional testing

### `extended_noisy_chase`

- rule:
  - `TS_20 > 0`
  - `TS_50 > 0`
  - stretched from mean
  - upper-band area
  - at least one cleanliness measure weak
- sample size: `51`
- performance:
  - `ret_10d mean = 6.07%`
  - `touch_up_2pct_10d = 88.24%`
  - `touch_down_2pct_10d = 66.67%`
- interpretation:
  - this is the most important “misleading by intuition” condition
  - extension plus imperfect cleanliness was not a reliable fade setup in BTC
  - in this sample, positive structure still dominated the negative narrative

### `regime_supported_upside`

- sample size: `10`
- performance:
  - weak realized edge despite favorable regime / hazard wording
- interpretation:
  - hazard / regime support alone is not enough
  - it still needs better structural or contextual confirmation

## What This Pass Suggests

- the best usable upside conditions are interaction-heavy, not single-family:
  - supportive trend
  - rebound skew
  - low shock context
  - on-chain or participation confirmation
- the best downside-avoidance condition is broad and regime-led:
  - `low_risk_base`
- pullback logic is not validated yet:
  - current pullback templates are weak or too sparse
- some “bad-looking” states are not actually bad:
  - extension inside supportive structure is not automatically a short-horizon bearish condition in BTC
- on-chain is most useful as a structural tailwind layer, not as a standalone tactical trigger

## Next-Step Recommendations

- carry forward the strongest usable interaction families for later walk-forward testing:
  - `structural_onchain_tailwind`
  - `upside_probability_stack`
  - `expansion_with_participation`
  - `low_risk_base`
- explicitly challenge intuitive but weak narratives later:
  - pullback-alone logic
  - hazard-only upside logic
- treat extension carefully:
  - use it as context, not as an automatic fade condition
- in the next pass, prefer interaction designs that separate:
  - high-upside / high-downside movement states
  - high-upside / controlled-downside states
