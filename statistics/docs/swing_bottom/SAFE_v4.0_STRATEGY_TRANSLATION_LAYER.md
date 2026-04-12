# SAFE v4.0 Strategy Translation Layer

## Purpose

This layer translates the promoted playbook into operational structural states: active context, waiting, conflict, no edge, and invalidation. It does not define orders, entries, exits, stops, position sizing, portfolio rules, PnL, or backtests.

## Inputs

- Source: `out/swing_bottom/swing_playbook_layer.csv`
- Uses: playbook label, attention level, edge clarity, conflict score, buy/sell timing spread, and playbook persistence fields.

## Operational Taxonomy

- `LONG_CONTEXT_ACTIVE`: `ACCUMULATION_WATCH` with high attention, clarity >= 0.30, conflict <= 0.22, and buy-dominant spread >= 0.15.
- `SELL_CONTEXT_ACTIVE`: `DISTRIBUTION_WATCH` with high attention, clarity >= 0.30, conflict <= 0.24, and sell-dominant spread <= -0.15.
- `WAIT_CONFIRMATION`: directional or transition context exists, but active-context requirements are not met.
- `STAND_ASIDE_CONFLICT`: high conflict/overlap invalidates directional interpretation.
- `STAND_ASIDE_NO_EDGE`: no structural edge is present.
- `CONTEXT_INVALIDATED`: a previously favorable context breaks into conflict/no-edge or flips to the opposite side.

## Operational-State Summary

| operational_state | row_count | row_share | avg_run_length_days | buy_zone_5_rate | sell_zone_5_rate | avg_clarity | avg_conflict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WAIT_CONFIRMATION | 1380.000 | 43.7% | 1.955 | 24.9% | 19.3% | 0.211 | 0.194 |
| SELL_CONTEXT_ACTIVE | 602.000 | 19.1% | 1.905 | 2.5% | 51.8% | 0.412 | 0.161 |
| STAND_ASIDE_NO_EDGE | 438.000 | 13.9% | 2.355 | 2.5% | 10.3% | 0.098 | 0.099 |
| CONTEXT_INVALIDATED | 353.000 | 11.2% | 1.000 | 12.2% | 17.0% | 0.105 | 0.177 |
| LONG_CONTEXT_ACTIVE | 228.000 | 7.2% | 1.288 | 50.9% | 0.9% | 0.370 | 0.156 |
| STAND_ASIDE_CONFLICT | 157.000 | 5.0% | 1.454 | 40.8% | 12.1% | 0.093 | 0.329 |

## Playbook Mapping

| operational_state | playbook_label | row_count | share_within_state |
| --- | --- | --- | --- |
| CONTEXT_INVALIDATED | HIGH_CONFLICT | 101 | 28.6% |
| CONTEXT_INVALIDATED | NO_ACTION | 252 | 71.4% |
| LONG_CONTEXT_ACTIVE | ACCUMULATION_WATCH | 228 | 100.0% |
| SELL_CONTEXT_ACTIVE | DISTRIBUTION_WATCH | 602 | 100.0% |
| STAND_ASIDE_CONFLICT | HIGH_CONFLICT | 157 | 100.0% |
| STAND_ASIDE_NO_EDGE | NO_ACTION | 438 | 100.0% |
| WAIT_CONFIRMATION | ACCUMULATION_WATCH | 88 | 6.4% |
| WAIT_CONFIRMATION | DISTRIBUTION_WATCH | 35 | 2.5% |
| WAIT_CONFIRMATION | TRANSITION_WATCH | 1257 | 91.1% |

## Transition Logic

The layer is intentionally state-machine-like. Favorable playbook states move into `WAIT_CONFIRMATION` first unless clarity and spread are strong enough for an active context. Active contexts can fall back to wait, stand aside, or `CONTEXT_INVALIDATED` when conflict rises, the edge disappears, or the opposite side becomes dominant. This captures forming, active, conflicted, and absent context without turning the layer into execution logic.

## Latest State

- Date: `2026-04-09`
- Operational state: `CONTEXT_INVALIDATED`
- Operational bias: `mixed`
- Note: Previously favorable context is invalidated by high conflict.

## Interpretation

This layer is a useful bridge from human-readable playbook labels toward later strategy design because it separates permission, deferral, caution, and invalidation. It should be treated as a structural translation layer only. Later strategy work can consume these states, but this report makes no claim about tradability or execution performance.

## Output Files

- `out/swing_bottom/strategy_translation_layer.csv`
- `out/swing_bottom/strategy_translation_summary.csv`
