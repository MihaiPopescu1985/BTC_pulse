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
| NO_SIGNAL | 2440.000 | 72.0% | 5.270 | 20.8% | 18.1% | 0.172 | 0.181 |
| SELL_SIGNAL_NEW | 315.000 | 9.3% | 1.000 | 0.6% | 52.7% | 0.391 | 0.161 |
| SELL_SIGNAL_ACTIVE | 238.000 | 7.0% | 1.789 | 2.1% | 57.1% | 0.400 | 0.163 |
| LONG_SIGNAL_NEW | 181.000 | 5.3% | 1.000 | 52.5% | 0.0% | 0.372 | 0.159 |
| SIGNAL_INVALIDATED | 153.000 | 4.5% | 1.000 | 15.0% | 21.6% | 0.129 | 0.182 |
| LONG_SIGNAL_ACTIVE | 61.000 | 1.8% | 1.245 | 54.1% | 1.6% | 0.379 | 0.164 |

## Signal Context Runs

| signal_side | avg_context_run_length_days | context_run_count |
| --- | --- | --- |
| long | 1.337 | 181.000 |
| sell | 1.756 | 315.000 |

## Rule-State Mapping

| signal_state | rule_state | row_count | share_within_signal_state |
| --- | --- | --- | --- |
| LONG_SIGNAL_ACTIVE | LONG_ELIGIBLE | 61 | 100.0% |
| LONG_SIGNAL_NEW | LONG_ELIGIBLE | 181 | 100.0% |
| NO_SIGNAL | AWAIT_CONFIRMATION | 1586 | 65.0% |
| NO_SIGNAL | BLOCKED_BY_CONFLICT | 145 | 5.9% |
| NO_SIGNAL | BLOCKED_NO_EDGE | 453 | 18.6% |
| NO_SIGNAL | INVALIDATED | 256 | 10.5% |
| SELL_SIGNAL_ACTIVE | SELL_ELIGIBLE | 238 | 100.0% |
| SELL_SIGNAL_NEW | SELL_ELIGIBLE | 315 | 100.0% |
| SIGNAL_INVALIDATED | INVALIDATED | 153 | 100.0% |

## Event Logic

The state machine emits `*_SIGNAL_NEW` only when an eligible context starts. Consecutive eligible days on the same side become `*_SIGNAL_ACTIVE`, not repeated new events. `SIGNAL_INVALIDATED` is emitted only when a previously active signal context is followed by explicit invalidation. Awaiting, blocked, or no-edge rows otherwise become `NO_SIGNAL`.

## Latest Signal State

- Date: `2026-11-25`
- Signal state: `NO_SIGNAL`
- Signal side: `none`
- Long event: `0`
- Sell event: `0`
- Invalidation event: `0`
- Note: Rule layer is awaiting confirmation; no signal is realized.

## Interpretation

This is the first bridge from structural permission into discrete signal events. It is useful for later strategy construction because it separates onset, continuation, invalidation, and absence of signal. It remains non-executable: signal events are structural markers, not orders.

## Output Files

- `out/swing_bottom/signal_layer.csv`
- `out/swing_bottom/signal_layer_summary.csv`
