# SAFE v4.0 On-Chain Interpretive Audit

## Scope
This audit covers the active production-facing on-chain indicators:

- `ONCHAIN_VOL_Z`
- `ONCHAIN_DOM_Z`
- `ONCHAIN_WHALE_SHARE_Z`
- `ONCHAIN_AMOUNT_PCT`
- `ONCHAIN_WHALE_TX_PCT`
- `ONCHAIN_DOM_PCT`

These are exported by [run_onchain_features.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_onchain_features.py) into [onchain_features.csv](/home/mihai/Documents/BTC_pulse/statistics/out/onchain_features.csv).

This family should not be judged only by short-horizon direct prediction.
Its natural role is often:

- structural context
- regime backdrop
- slow flow shift
- unusual network / coin-movement behavior

## Raw sources and construction

The on-chain layer is built from:

- [daily_amounts.json](/home/mihai/Documents/BTC_pulse/statistics/data/daily_amounts.json)
  - total transferred amount
- [daily_tx_size.json](/home/mihai/Documents/BTC_pulse/statistics/data/daily_tx_size.json)
  - transaction-count buckets by size

Derived internal on-chain fields include:

- `ONCHAIN_AMOUNT_TOTAL`
- `ONCHAIN_AMOUNT_LOG`
- `ONCHAIN_TX_WHALE`
- `ONCHAIN_TX_MID`
- `ONCHAIN_TX_SMALL`
- `ONCHAIN_WHALE_SHARE`
- `ONCHAIN_DOMINANCE`

The active production-facing fields in scope are built from those raw components.

## Repository usage

### Productive path
- [run_onchain_features.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_onchain_features.py)
  - computes and exports the on-chain feature surface

### Current productive models
- no current direct use in `src/core/`
- no current direct use in `src/models/`

### Research usage
- all six active on-chain fields remain available in the retained research feature surface

Current status:

- production-facing descriptive export
- research / interpretive context
- not yet integrated into the retained swing-structure bridge

## Family overview

### 1. Activity intensity anomaly
- `ONCHAIN_VOL_Z`

This measures whether transferred amount is unusually high or low relative to its rolling history.

Story:

- unusual network flow intensity
- broad on-chain activity regime shift

### 2. Dominance anomaly
- `ONCHAIN_DOM_Z`

This measures whether whale+mid dominance versus small transactions is unusual relative to its history.

Story:

- unusual large-actor influence
- structural shift in transaction composition

### 3. Whale share anomaly
- `ONCHAIN_WHALE_SHARE_Z`

This measures whether the whale-share of transaction counts is unusually high or low relative to history.

Story:

- unusual whale presence or withdrawal
- potential structural stress or concentration shift

### 4. Raw percentage-change flow features
- `ONCHAIN_AMOUNT_PCT`
- `ONCHAIN_WHALE_TX_PCT`
- `ONCHAIN_DOM_PCT`

These measure day-over-day changes in:

- total transferred amount
- whale transaction count
- whale/mid dominance

Story:

- very short-horizon on-chain flow shock

But these are likely noisier than the z-score-style features.

## Per-indicator audit

### `ONCHAIN_VOL_Z`
- Measures:
  - z-score of log amount transferred.
- Market story:
  - unusual overall flow intensity.
- Overlap:
  - overlaps with `ONCHAIN_DOM_Z` because both can rise in structurally active environments.
- Overlap quality:
  - useful overlap.
  - total flow intensity is not the same thing as whale concentration.
- Assessment:
  - structurally useful.
  - not a direct tactical entry trigger, but plausible macro / regime context.
- Classification:
  - `productive_context`

### `ONCHAIN_DOM_Z`
- Measures:
  - z-score of on-chain dominance ratio.
- Market story:
  - unusual concentration of whale+mid activity relative to small activity.
- Overlap:
  - overlaps partly with `ONCHAIN_WHALE_SHARE_Z`, but the dominance ratio is broader than whale share alone.
- Overlap quality:
  - useful overlap.
- Assessment:
  - strongest direct upside-context on-chain feature in the current evidence.
  - likely better as structural / regime filter than as a stand-alone tactical signal.
- Classification:
  - `productive_context`

### `ONCHAIN_WHALE_SHARE_Z`
- Measures:
  - z-score of whale-share of transactions.
- Market story:
  - unusual whale participation share.
- Overlap:
  - overlaps with `ONCHAIN_DOM_Z`, but is more narrowly whale-focused.
- Overlap quality:
  - useful overlap.
- Assessment:
  - the clearest downside-structural on-chain feature in current evidence.
  - more informative for risk / stress background than for upside timing.
- Classification:
  - `productive_context`

### `ONCHAIN_AMOUNT_PCT`
- Measures:
  - day-over-day percent change in transferred amount.
- Market story:
  - very short-horizon flow shock.
- Overlap:
  - overlaps with `ONCHAIN_VOL_Z`, but without the long-window normalization.
- Overlap quality:
  - weak overlap value.
  - the normalized z-score version appears materially more useful.
- Assessment:
  - noisy and unstable.
  - plausible as a very short-term flow shock descriptor, but weak on its own.
- Classification:
  - `challenge_later`

### `ONCHAIN_WHALE_TX_PCT`
- Measures:
  - day-over-day percent change in whale transaction count.
- Market story:
  - short-horizon whale activity jump or drop.
- Overlap:
  - overlaps with whale-share and dominance measures, but in a much noisier way.
- Overlap quality:
  - mostly weak.
- Assessment:
  - weakest active on-chain feature in current evidence.
  - conceptually interesting, but too noisy to trust at face value.
- Classification:
  - `challenge_later`

### `ONCHAIN_DOM_PCT`
- Measures:
  - day-over-day percent change in dominance ratio.
- Market story:
  - short-horizon change in large-actor dominance.
- Overlap:
  - overlaps with `ONCHAIN_DOM_Z`, but without smoothing or normalization.
- Overlap quality:
  - weak.
- Assessment:
  - looks more like a noisy flow-shift feature than a stable structural descriptor.
- Classification:
  - `challenge_later`

## Story-quality assessment

### Strongest structural / regime context
- `ONCHAIN_DOM_Z`
- `ONCHAIN_VOL_Z`
- `ONCHAIN_WHALE_SHARE_Z`

These are the meaningful on-chain context layer.

### Best downside-structural context
- `ONCHAIN_WHALE_SHARE_Z`

This looks most tied to downside excursion / downside touch behavior.

### Best upside-structural context
- `ONCHAIN_DOM_Z`

This looks strongest for upside excursion and touch context.

### Weakest family members
- `ONCHAIN_WHALE_TX_PCT`
- `ONCHAIN_DOM_PCT`
- `ONCHAIN_AMOUNT_PCT`

These are not automatically useless, but they look too noisy to trust as first-line features.

## Initial classification summary

### Productive core
- none yet

### Productive context
- `ONCHAIN_VOL_Z`
- `ONCHAIN_DOM_Z`
- `ONCHAIN_WHALE_SHARE_Z`

### Research context
- none

### Redundant alias
- none

### Suspect or misleading
- none yet

### Challenge later
- `ONCHAIN_AMOUNT_PCT`
- `ONCHAIN_WHALE_TX_PCT`
- `ONCHAIN_DOM_PCT`

## Guidance for future walk-forward use

- On-chain should be treated primarily as slow structural context, not as a fast trigger layer.
- Prefer the z-score-style on-chain indicators over the raw percentage-change fields.
- Most promising later interaction roles:
  - `ONCHAIN_DOM_Z` with trend / regime strength
  - `ONCHAIN_WHALE_SHARE_Z` with downside risk / shock context
  - `ONCHAIN_VOL_Z` with broad volatility / expansion context
- Do not expect on-chain alone to compete with trend or position for short-horizon timing.
