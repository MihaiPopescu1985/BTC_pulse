# SAFE v4.0 Swing Playbook Layer

## Purpose

- maps decision states into human-readable operational playbook interpretations
- remains structural: no orders, entries, exits, position sizing, or PnL logic
- designed for dashboard and daily-report interpretation

## Playbook Labels

- `ACCUMULATION_WATCH`: buy-side swing-low opportunity is structurally favored; monitor, not a trade trigger
- `DISTRIBUTION_WATCH`: sell-side swing-high opportunity is structurally favored; monitor, not an exit rule
- `HIGH_CONFLICT`: buy and sell timing overlap; mixed structure requires caution
- `TRANSITION_WATCH`: timing is forming or resolving, but clarity is not sufficient
- `NO_ACTION`: no clear swing-timing edge

## Mapping Logic

- uses `decision_state`, promoted buy/sell timing scores, `edge_clarity_score`, `conflict_score`, and state persistence
- clear buy/sell decision states map to watch labels only when clarity is sufficient and conflict is controlled
- conflict and unclear decision states become explicit caution labels
- neutral states become inactivity labels, with persistent neutral periods marked as very-low attention

## Playbook Prevalence And Quality

- `ACCUMULATION_WATCH`: share `0.108`, avg run `1.45` days, buy-zone 5% `0.545`, sell-zone 5% `0.003`, clarity `0.346`, conflict `0.164`
- `DISTRIBUTION_WATCH`: share `0.188`, avg run `1.92` days, buy-zone 5% `0.019`, sell-zone 5% `0.534`, clarity `0.384`, conflict `0.166`
- `HIGH_CONFLICT`: share `0.072`, avg run `1.39` days, buy-zone 5% `0.383`, sell-zone 5% `0.218`, clarity `0.083`, conflict `0.305`
- `TRANSITION_WATCH`: share `0.421`, avg run `1.92` days, buy-zone 5% `0.236`, sell-zone 5% `0.202`, clarity `0.199`, conflict `0.196`
- `NO_ACTION`: share `0.211`, avg run `2.11` days, buy-zone 5% `0.035`, sell-zone 5% `0.132`, clarity `0.100`, conflict `0.108`

## Decision-State Mapping

- `ACCUMULATION_WATCH` <- `BUY_SETUP`: `367` rows
- `DISTRIBUTION_WATCH` <- `SELL_SETUP`: `638` rows
- `HIGH_CONFLICT` <- `CONFLICT_OVERLAP`: `243` rows
- `NO_ACTION` <- `NEUTRAL_NO_EDGE`: `714` rows
- `TRANSITION_WATCH` <- `TRANSITION_UNCLEAR`: `996` rows
- `TRANSITION_WATCH` <- `BUY_SETUP`: `326` rows
- `TRANSITION_WATCH` <- `SELL_SETUP`: `104` rows

## Current Row

- date: `2026-11-25`
- close: `59232.01`
- decision state: `BUY_SETUP`
- playbook label: `TRANSITION_WATCH`
- attention: `medium`
- note: Buy setup present but clarity is modest or conflict is elevated; monitor for cleaner structure.

## Interpretive Usefulness

- the playbook layer adds stable human-readable bias, attention level, and note fields on top of raw decision states
- it separates watch states from caution states and inactivity states without creating trade mechanics
- this layer is suitable for dashboard review and daily structural interpretation; later strategy work must validate any operational use separately
