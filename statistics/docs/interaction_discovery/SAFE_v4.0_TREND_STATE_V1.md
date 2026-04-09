# SAFE v4.0 Trend State V1

## Purpose
`trend_state_v1` is a research-stage, rule-based layer that converts the validated trend-family indicators into compact market-state labels.

It is intended to support future walk-forward refinement by answering questions such as:

- is the market structurally supportive or weak?
- is the move clean or noisy?
- is the market pulling back inside support, or only bouncing inside weak structure?
- is the move early, extended, or mostly chop?

This layer is not yet integrated into the productive `src/core/` or accepted `src/walkforward/` paths.

## File locations

- Script:
  - [trend_state_v1.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/core/interaction_discovery/trend_state_v1.py)
- Output:
  - [trend_state_v1.csv](/home/mihai/Documents/BTC_pulse/statistics/out/trend_state_v1.csv)

## Inputs used

Backbone trend structure:

- `TS_20`
- `TS_50`
- `TS_200`
- `ER_20`
- `ER_50`

Context:

- `R_14`
- `R_7`
- `LR_20`

Excluded on purpose:

- `RVR_20`
- `RVR_50`
- `RVR_200`

Reason:

- the trend-family audit and reliability evidence both showed `RVR_*` is redundant with `TS_*` in the current implementation

## Why these indicators were chosen

### `TS_20`, `TS_50`, `TS_200`
These form the directional structure backbone.

- `TS_20`: short-term directional pressure
- `TS_50`: medium structure health
- `TS_200`: long backdrop / major bias

### `ER_20`, `ER_50`
These measure trend cleanliness.

- `ER_20`: short-horizon path cleanliness
- `ER_50`: medium-horizon path cleanliness and the strongest underused trend-family indicator in the reliability report

### `R_14`, `R_7`
These provide recent move context.

- `R_14`: better short swing / pullback context
- `R_7`: faster weekly move context

### `LR_20`
This is used only as shape confirmation / divergence context.

It is not the backbone. It helps confirm when short structure is still sloping constructively even if recent returns are mixed.

## State design

The classifier outputs:

- `trend_state_v1`
- `trend_context_v1`

Optional debugging flags are also exported:

- `supportive_structure_flag`
- `weak_backdrop_flag`
- `clean_trend_flag`
- `noisy_trend_flag`
- `pullback_flag`
- `rebound_attempt_flag`
- `extended_move_flag`

## Threshold style

The rules are deterministic and simple.

They use:

- sign logic on `TS_*`
- percentile-rank thresholds computed from the current history
- a few explicit absolute checks on `ER_*` and recent returns

This keeps the state logic readable without introducing model fitting.

## Main state definitions

### `STRONG_CLEAN_UPTREND`
Meaning:

- medium and long structure are supportive
- short trend is aligned
- trend cleanliness is high
- the move is not currently a pullback and not already heavily extended

Interpretation:

- best pure continuation state in this first version

### `NOISY_UPTREND`
Meaning:

- medium and long structure are supportive
- but cleanliness is not strong enough

Interpretation:

- structure is positive, but chase quality is lower

### `PULLBACK_IN_UPTREND`
Meaning:

- broader structure is supportive
- recent returns are weak enough to qualify as a pullback
- medium-horizon cleanliness is still acceptable

Interpretation:

- potential opportunity state for later walk-forward use

### `WEAK_UPTREND`
Meaning:

- supportive structure exists
- cleanliness is acceptable
- but not strong enough to qualify as a strong clean continuation

Interpretation:

- constructive but lower-conviction trend support

### `CHOPPY_NEUTRAL`
Meaning:

- neither side has convincing structure
- both `ER_20` and `ER_50` are low enough to indicate chop

Interpretation:

- no strong directional trend story

### `BEARISH_PRESSURE`
Meaning:

- medium and long structure are both weak
- no convincing rebound state is present

Interpretation:

- weak or pressured backdrop

### `CLEAN_REBOUND_ATTEMPT`
Meaning:

- long/medium backdrop is weak
- but short trend and slope have turned positive
- short cleanliness is acceptable

Interpretation:

- rebound state inside a still-weak backdrop

### `FAILED_BOUNCE_OR_WEAK_STRUCTURE`
Meaning:

- residual weak / mixed state
- not clean enough to be constructive
- not coherent enough to be neutral chop
- not clearly structured enough to be a rebound state

Interpretation:

- transitional but fragile state

## Context label definitions

### `EARLY_MOVE`
Used when:

- trend is clean
- recent returns are positive
- the move does not already look extended

Meaning:

- a relatively fresh directional move

### `PULLBACK`
Used when:

- structure is supportive
- recent return context is negative / soft

Meaning:

- dip or retracement inside broader support

### `EXTENDED`
Used when:

- `R_7` or `R_14` is in a high percentile
- especially when short trend is already positive

Meaning:

- move may already be stretched

### `CHOP`
Default context when no cleaner pattern is present

Meaning:

- no strong recent move condition

### `REBOUND_ATTEMPT`
Used when:

- the short move is turning positive
- but the broader backdrop is still weak

Meaning:

- short recovery attempt, not full repair

## Current output distribution

Latest run on the current BTC history produced:

### `trend_state_v1`

- `FAILED_BOUNCE_OR_WEAK_STRUCTURE`: `1098`
- `BEARISH_PRESSURE`: `671`
- `NOISY_UPTREND`: `502`
- `WEAK_UPTREND`: `270`
- `CHOPPY_NEUTRAL`: `259`
- `PULLBACK_IN_UPTREND`: `99`
- `STRONG_CLEAN_UPTREND`: `49`
- `CLEAN_REBOUND_ATTEMPT`: `3`
- warm-up / unavailable rows: `200`

### `trend_context_v1`

- `CHOP`: `2162`
- `EXTENDED`: `565`
- `PULLBACK`: `126`
- `EARLY_MOVE`: `69`
- `REBOUND_ATTEMPT`: `29`
- warm-up / unavailable rows: `200`

Latest snapshot:

- `trend_state_v1 = BEARISH_PRESSURE`
- `trend_context_v1 = CHOP`

## What this layer is for

This layer is meant to help the next walk-forward refinement ask better structured questions such as:

- does opportunity behave differently in `PULLBACK_IN_UPTREND` than in `NOISY_UPTREND`?
- is `ER_50` better used as a state discriminator than as a raw scalar?
- does `LR_20` help when it confirms or contradicts `TS_20`?
- does `R_14` improve timing by distinguishing pullback from extension?

## Limitations

- This is a first deterministic version, not a locked production contract.
- Thresholds are simple and history-relative, not optimized.
- The state set is intentionally compact, so some distinct situations are still grouped together.
- `FAILED_BOUNCE_OR_WEAK_STRUCTURE` is currently broad and likely needs later decomposition.
- `CLEAN_REBOUND_ATTEMPT` is rare in this first version, which means the current rebound rules are strict.
- This layer is descriptive and preparatory. It is not yet part of the accepted walk-forward decision path.

## Intended next use

The next reasonable use is not immediate integration.

The next use is to test whether:

- these states add value over raw trend scalars
- `ER_50` becomes more useful when expressed as state logic
- pullback states and rebound states improve opportunity ranking
- trend context can reduce noisy chase behavior in future walk-forward iterations
