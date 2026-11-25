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
| AWAIT_CONFIRMATION | 1586.000 | 46.8% | 2.126 | 25.3% | 19.7% | 0.207 | 0.195 | 0.0% |
| SELL_ELIGIBLE | 553.000 | 16.3% | 1.756 | 1.3% | 54.6% | 0.395 | 0.162 | 0.0% |
| BLOCKED_NO_EDGE | 453.000 | 13.4% | 2.618 | 2.2% | 9.7% | 0.098 | 0.098 | 100.0% |
| INVALIDATED | 409.000 | 12.1% | 1.017 | 14.2% | 22.2% | 0.133 | 0.169 | 100.0% |
| LONG_ELIGIBLE | 242.000 | 7.1% | 1.337 | 52.9% | 0.4% | 0.374 | 0.161 | 0.0% |
| BLOCKED_BY_CONFLICT | 145.000 | 4.3% | 1.381 | 42.1% | 18.6% | 0.079 | 0.312 | 100.0% |

## Operational Mapping

| rule_state | operational_state | row_count | share_within_rule_state |
| --- | --- | --- | --- |
| AWAIT_CONFIRMATION | WAIT_CONFIRMATION | 1586 | 100.0% |
| BLOCKED_BY_CONFLICT | STAND_ASIDE_CONFLICT | 145 | 100.0% |
| BLOCKED_NO_EDGE | STAND_ASIDE_NO_EDGE | 453 | 100.0% |
| INVALIDATED | CONTEXT_INVALIDATED | 359 | 87.8% |
| INVALIDATED | LONG_CONTEXT_ACTIVE | 22 | 5.4% |
| INVALIDATED | SELL_CONTEXT_ACTIVE | 28 | 6.8% |
| LONG_ELIGIBLE | LONG_CONTEXT_ACTIVE | 242 | 100.0% |
| SELL_ELIGIBLE | SELL_CONTEXT_ACTIVE | 553 | 100.0% |

## Transition Logic

The intended progression is blocked/no-edge -> await confirmation -> eligible. Eligible contexts can revert to await confirmation or become invalidated when the operational layer detects conflict, no edge, or a broken prior context. This is a permission/block layer only; it deliberately stops before trade construction.

## Latest Rule State

- Date: `2026-11-25`
- Rule state: `AWAIT_CONFIRMATION`
- Long permission: `0`
- Sell/de-risk permission: `0`
- Block action: `0`
- Note: Directional context exists but explicit eligibility rules are not satisfied.

## Interpretation

The rule layer is a meaningful bridge toward later strategy design because it separates structural permission from confirmation, block, and invalidation. It remains non-executable: permission means a later strategy may consider that side, not that the system should place an order.

## Output Files

- `out/swing_bottom/rule_layer.csv`
- `out/swing_bottom/rule_layer_summary.csv`
