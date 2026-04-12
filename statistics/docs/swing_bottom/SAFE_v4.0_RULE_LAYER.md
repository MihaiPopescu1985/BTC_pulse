# SAFE v4.0 Minimal Rule Layer

## Purpose

This layer translates operational states into explicit structural permissions, waits, blocks, and invalidations. It does not define order execution, entries/exits, stops, position sizing, portfolio logic, PnL, or backtests.

## Inputs

- Source: `out/swing_bottom/strategy_translation_layer.csv`
- Uses: operational state, operational bias, readiness flag, caution flag, invalidation flag, stand-aside flag, and operational-state persistence.

## Rule Taxonomy

- `LONG_ELIGIBLE`: active long context with readiness, no caution, long bias, and operational-state age >= 1 day.
- `SELL_ELIGIBLE`: active sell/de-risk context with readiness, no caution, sell bias, and operational-state age >= 1 day.
- `AWAIT_CONFIRMATION`: context exists but eligibility or persistence requirements are not satisfied.
- `BLOCKED_BY_CONFLICT`: conflict/stand-aside structure blocks directional action.
- `BLOCKED_NO_EDGE`: no structural edge is present.
- `INVALIDATED`: a previously favorable context has broken.

## Rule-State Summary

| rule_state | row_count | row_share | avg_run_length_days | buy_zone_5_rate | sell_zone_5_rate | avg_clarity | avg_conflict | block_action_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AWAIT_CONFIRMATION | 1380.000 | 43.7% | 1.955 | 24.9% | 19.3% | 0.211 | 0.194 | 0.0% |
| SELL_ELIGIBLE | 581.000 | 18.4% | 1.893 | 2.6% | 51.6% | 0.413 | 0.162 | 0.0% |
| BLOCKED_NO_EDGE | 438.000 | 13.9% | 2.355 | 2.5% | 10.3% | 0.098 | 0.099 | 100.0% |
| INVALIDATED | 395.000 | 12.5% | 1.021 | 13.9% | 18.2% | 0.133 | 0.174 | 100.0% |
| LONG_ELIGIBLE | 207.000 | 6.6% | 1.302 | 50.2% | 1.0% | 0.373 | 0.156 | 0.0% |
| BLOCKED_BY_CONFLICT | 157.000 | 5.0% | 1.454 | 40.8% | 12.1% | 0.093 | 0.329 | 100.0% |

## Operational Mapping

| rule_state | operational_state | row_count | share_within_rule_state |
| --- | --- | --- | --- |
| AWAIT_CONFIRMATION | WAIT_CONFIRMATION | 1380 | 100.0% |
| BLOCKED_BY_CONFLICT | STAND_ASIDE_CONFLICT | 157 | 100.0% |
| BLOCKED_NO_EDGE | STAND_ASIDE_NO_EDGE | 438 | 100.0% |
| INVALIDATED | CONTEXT_INVALIDATED | 353 | 89.4% |
| INVALIDATED | LONG_CONTEXT_ACTIVE | 21 | 5.3% |
| INVALIDATED | SELL_CONTEXT_ACTIVE | 21 | 5.3% |
| LONG_ELIGIBLE | LONG_CONTEXT_ACTIVE | 207 | 100.0% |
| SELL_ELIGIBLE | SELL_CONTEXT_ACTIVE | 581 | 100.0% |

## Transition Logic

The intended progression is blocked/no-edge -> await confirmation -> eligible. Eligible contexts can revert to await confirmation or become invalidated when the operational layer detects conflict, no edge, or a broken prior context. This is a permission/block layer only; it deliberately stops before trade construction.

## Latest Rule State

- Date: `2026-04-09`
- Rule state: `INVALIDATED`
- Long permission: `0`
- Sell/de-risk permission: `0`
- Block action: `1`
- Note: Previously favorable context is broken; structural action is blocked until a new context forms.

## Interpretation

The rule layer is a meaningful bridge toward later strategy design because it separates structural permission from confirmation, block, and invalidation. It remains non-executable: permission means a later strategy may consider that side, not that the system should place an order.

## Output Files

- `out/swing_bottom/rule_layer.csv`
- `out/swing_bottom/rule_layer_summary.csv`
