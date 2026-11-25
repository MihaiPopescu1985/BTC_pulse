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
| WAIT_CONFIRMATION | 1586.000 | 46.8% | 2.126 | 25.3% | 19.7% | 0.207 | 0.195 |
| SELL_CONTEXT_ACTIVE | 581.000 | 17.1% | 1.793 | 1.2% | 54.6% | 0.395 | 0.161 |
| STAND_ASIDE_NO_EDGE | 453.000 | 13.4% | 2.618 | 2.2% | 9.7% | 0.098 | 0.098 |
| CONTEXT_INVALIDATED | 359.000 | 10.6% | 1.000 | 13.1% | 21.2% | 0.099 | 0.173 |
| LONG_CONTEXT_ACTIVE | 264.000 | 7.8% | 1.327 | 52.7% | 0.4% | 0.373 | 0.159 |
| STAND_ASIDE_CONFLICT | 145.000 | 4.3% | 1.381 | 42.1% | 18.6% | 0.079 | 0.312 |

## Playbook Mapping

| operational_state | playbook_label | row_count | share_within_state |
| --- | --- | --- | --- |
| CONTEXT_INVALIDATED | HIGH_CONFLICT | 98 | 27.3% |
| CONTEXT_INVALIDATED | NO_ACTION | 261 | 72.7% |
| LONG_CONTEXT_ACTIVE | ACCUMULATION_WATCH | 264 | 100.0% |
| SELL_CONTEXT_ACTIVE | DISTRIBUTION_WATCH | 581 | 100.0% |
| STAND_ASIDE_CONFLICT | HIGH_CONFLICT | 145 | 100.0% |
| STAND_ASIDE_NO_EDGE | NO_ACTION | 453 | 100.0% |
| WAIT_CONFIRMATION | ACCUMULATION_WATCH | 103 | 6.5% |
| WAIT_CONFIRMATION | DISTRIBUTION_WATCH | 57 | 3.6% |
| WAIT_CONFIRMATION | TRANSITION_WATCH | 1426 | 89.9% |

## Transition Logic

The layer is intentionally state-machine-like. Favorable playbook states move into `WAIT_CONFIRMATION` first unless clarity and spread are strong enough for an active context. Active contexts can fall back to wait, stand aside, or `CONTEXT_INVALIDATED` when conflict rises, the edge disappears, or the opposite side becomes dominant. This captures forming, active, conflicted, and absent context without turning the layer into execution logic.

## Latest State

- Date: `2026-11-25`
- Operational state: `WAIT_CONFIRMATION`
- Operational bias: `long_lean`
- Note: Structure is forming but not confirmed; defer directional interpretation.

## Interpretation

This layer is a useful bridge from human-readable playbook labels toward later strategy design because it separates permission, deferral, caution, and invalidation. It should be treated as a structural translation layer only. Later strategy work can consume these states, but this report makes no claim about tradability or execution performance.

## Output Files

- `out/swing_bottom/strategy_translation_layer.csv`
- `out/swing_bottom/strategy_translation_summary.csv`
