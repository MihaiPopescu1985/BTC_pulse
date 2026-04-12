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

- `ACCUMULATION_WATCH`: share `0.100`, avg run `1.44` days, buy-zone 5% `0.547`, sell-zone 5% `0.006`, clarity `0.344`, conflict `0.161`
- `DISTRIBUTION_WATCH`: share `0.202`, avg run `1.98` days, buy-zone 5% `0.027`, sell-zone 5% `0.507`, clarity `0.405`, conflict `0.164`
- `HIGH_CONFLICT`: share `0.082`, avg run `1.50` days, buy-zone 5% `0.372`, sell-zone 5% `0.136`, clarity `0.096`, conflict `0.323`
- `TRANSITION_WATCH`: share `0.398`, avg run `1.77` days, buy-zone 5% `0.227`, sell-zone 5% `0.203`, clarity `0.205`, conflict `0.195`
- `NO_ACTION`: share `0.218`, avg run `2.04` days, buy-zone 5% `0.032`, sell-zone 5% `0.129`, clarity `0.101`, conflict `0.107`

## Decision-State Mapping

- `ACCUMULATION_WATCH` <- `BUY_SETUP`: `316` rows
- `DISTRIBUTION_WATCH` <- `SELL_SETUP`: `637` rows
- `HIGH_CONFLICT` <- `CONFLICT_OVERLAP`: `258` rows
- `NO_ACTION` <- `NEUTRAL_NO_EDGE`: `690` rows
- `TRANSITION_WATCH` <- `TRANSITION_UNCLEAR`: `878` rows
- `TRANSITION_WATCH` <- `BUY_SETUP`: `264` rows
- `TRANSITION_WATCH` <- `SELL_SETUP`: `115` rows

## Current Row

- date: `2026-04-09`
- close: `71945.71`
- decision state: `CONFLICT_OVERLAP`
- playbook label: `HIGH_CONFLICT`
- attention: `high`
- note: Buy and sell timing are both elevated; mixed structure, avoid single-sided interpretation.

## Interpretive Usefulness

- the playbook layer adds stable human-readable bias, attention level, and note fields on top of raw decision states
- it separates watch states from caution states and inactivity states without creating trade mechanics
- this layer is suitable for dashboard review and daily structural interpretation; later strategy work must validate any operational use separately
