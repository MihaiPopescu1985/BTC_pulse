# SAFE v4.0 Signal Realization Layer

## Purpose

This layer converts calibrated rule permissions into discrete structural signal events. It does not define execution, entries/exits, stops, position sizing, portfolio logic, PnL, or backtests.

## Inputs

- Source: `out/swing_bottom/rule_layer.csv`
- Uses: rule state, permission flags, confirmation flag, invalidation flag, block flag, and prior signal context.

## Signal Taxonomy

- `LONG_SIGNAL_NEW`: first day of a realized long-side signal context.
- `LONG_SIGNAL_ACTIVE`: continuation of an already-realized long-side signal context.
- `SELL_SIGNAL_NEW`: first day of a realized sell/de-risk signal context.
- `SELL_SIGNAL_ACTIVE`: continuation of an already-realized sell/de-risk signal context.
- `SIGNAL_INVALIDATED`: a previously active signal context is explicitly invalidated.
- `NO_SIGNAL`: no discrete signal event is active.

## Signal-State Summary

| signal_state | row_count | row_share | avg_run_length_days | buy_zone_5_rate | sell_zone_5_rate | avg_clarity | avg_conflict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NO_SIGNAL | 2225.000 | 70.5% | 5.045 | 20.0% | 16.8% | 0.171 | 0.182 |
| SELL_SIGNAL_NEW | 307.000 | 9.7% | 1.000 | 2.0% | 52.1% | 0.401 | 0.159 |
| SELL_SIGNAL_ACTIVE | 273.000 | 8.6% | 2.007 | 3.3% | 50.9% | 0.425 | 0.166 |
| LONG_SIGNAL_NEW | 159.000 | 5.0% | 1.000 | 49.7% | 0.6% | 0.370 | 0.156 |
| SIGNAL_INVALIDATED | 146.000 | 4.6% | 1.000 | 21.2% | 20.5% | 0.139 | 0.189 |
| LONG_SIGNAL_ACTIVE | 48.000 | 1.5% | 1.200 | 50.0% | 2.1% | 0.382 | 0.159 |

## Signal Context Runs

| signal_side | avg_context_run_length_days | context_run_count |
| --- | --- | --- |
| long | 1.302 | 159.000 |
| sell | 1.889 | 307.000 |

## Rule-State Mapping

| signal_state | rule_state | row_count | share_within_signal_state |
| --- | --- | --- | --- |
| LONG_SIGNAL_ACTIVE | LONG_ELIGIBLE | 48 | 100.0% |
| LONG_SIGNAL_NEW | LONG_ELIGIBLE | 159 | 100.0% |
| NO_SIGNAL | AWAIT_CONFIRMATION | 1376 | 61.8% |
| NO_SIGNAL | BLOCKED_BY_CONFLICT | 160 | 7.2% |
| NO_SIGNAL | BLOCKED_NO_EDGE | 438 | 19.7% |
| NO_SIGNAL | INVALIDATED | 251 | 11.3% |
| SELL_SIGNAL_ACTIVE | SELL_ELIGIBLE | 273 | 100.0% |
| SELL_SIGNAL_NEW | SELL_ELIGIBLE | 307 | 100.0% |
| SIGNAL_INVALIDATED | INVALIDATED | 146 | 100.0% |

## Event Logic

The state machine emits `*_SIGNAL_NEW` only when an eligible context starts. Consecutive eligible days on the same side become `*_SIGNAL_ACTIVE`, not repeated new events. `SIGNAL_INVALIDATED` is emitted only when a previously active signal context is followed by explicit invalidation. Awaiting, blocked, or no-edge rows otherwise become `NO_SIGNAL`.

## Latest Signal State

- Date: `2026-04-09`
- Signal state: `SIGNAL_INVALIDATED`
- Signal side: `sell`
- Long event: `0`
- Sell event: `0`
- Invalidation event: `1`
- Note: Previously active sell signal context is invalidated.

## Interpretation

This is the first bridge from structural permission into discrete signal events. It is useful for later strategy construction because it separates onset, continuation, invalidation, and absence of signal. It remains non-executable: signal events are structural markers, not orders.

## Output Files

- `out/swing_bottom/signal_layer.csv`
- `out/swing_bottom/signal_layer_summary.csv`
