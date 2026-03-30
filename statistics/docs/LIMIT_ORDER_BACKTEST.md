# Limit Order Backtest

This tool backtests a BTC-only passive long workflow using an explicit daily
state machine:

- `FLAT`
- `PENDING_ENTRY`
- `LONG_OPEN`

The old one-day forced-exit model was too restrictive for the intended strategy.
This patch replaces it with a daily reassessment flow where pending orders can
persist and open positions can carry overnight until they are stopped, hit a
target, or are closed by the next morning's SAFE reading.

## Why the previous model was wrong

The earlier engine forced a same-day close if an entry was filled and neither
target nor stop resolved cleanly within that day. That was a bad fit because:

- daily OHLC candles do not preserve intraday ordering
- same-day entry and target can be ambiguous when the order was not active from
  the session open
- a hard same-day close is artificial for this strategy
- a hard max-hold-days rule is also artificial for this strategy

## No-lookahead rule

For each day `D`:

- the morning plan for day `D` is built only from information known at the
  close of day `D-1`
- entry filters and reassessment exits use only the `D-1` SAFE row
- day `D` OHLC is used only for execution simulation

## State machine

Allowed transitions:

- `FLAT -> PENDING_ENTRY`
- `PENDING_ENTRY -> PENDING_ENTRY`
- `PENDING_ENTRY -> LONG_OPEN`
- `PENDING_ENTRY -> FLAT`
- `LONG_OPEN -> LONG_OPEN`
- `LONG_OPEN -> FLAT`

## Morning reassessment logic

### If flat

The engine can create a new pending buy limit from the latest finished close if
the selected SAFE gates pass.

### If a pending entry exists

The engine can:

- keep the pending order
- replace it using the latest finished close
- cancel it
- expire it after `entry_ttl_days`

Current modes:

- `--pending-order-update-mode replace`
  Recomputes the entry every morning from the latest finished close.
- `--pending-order-update-mode keep`
  Carries the same order forward until fill, cancellation, or TTL expiry.

### If a long position is open

Each morning the engine can:

- keep the position unchanged
- or exit at the new day open if a reassessment rule fires

Current reassessment exit options:

- `--reassess-open-on-hard-risk-off`
- `--reassess-open-on-rebound-lte-correction`
- `--reassess-open-on-regime-break`

## Order geometry

Base long-only geometry:

- `entry = prev_close * (1 - entry_offset_pct)`
- `target = entry_fill * (1 + target_offset_pct)`
- `stop = entry_fill * (1 - stop_offset_pct)`

Targets and stops are set from the actual fill price, not just from the posted
limit.

## Ambiguity handling

The important distinction is whether the position was already active from the
start of the daily session.

### Case A: order active from the session open

If `open <= entry_limit`, the long is active from the start of the session.
Then same-day target/stop evaluation against that day's range is acceptable.

If both target and stop are reachable, this is counted as:

- `ambiguous_stop_target_same_day`

Resolved by `fill_mode`:

- `pessimistic` -> stop
- `optimistic` -> target
- `skip_ambiguous` -> conservative stop, but ambiguity is still counted

### Case B: entry happens intraday

If `open > entry_limit` and later `low <= entry_limit`, the entry is intraday.

For long trades:

- if the same day reaches the stop, the stop is treated as definite because the
  price must pass through the entry before a lower stop
- if the same day reaches the target, same-day target recognition is ambiguous,
  because the target may have happened before the entry

This is counted as:

- `ambiguous_entry_exit_same_day`

Resolved by `fill_mode`:

- `optimistic` -> take the target
- `pessimistic` -> carry the position and ignore same-day target recognition
- `skip_ambiguous` -> same conservative carry behavior, while still counting the ambiguity

## Force end-of-day exit

Same-day forced exit is no longer the default.

Use:

- `--force-eod-exit`

only if you explicitly want the old behavior.

## Outputs

Outputs are written under `statistics/out/limit_order_backtest/`:

- `report.json`
- `trades.csv`
- `config_used.json`

Search mode also writes:

- `search_results.csv`

The report now includes lifecycle counts such as:

- `pending_created`
- `pending_replaced`
- `pending_canceled`
- `pending_expired`
- `entry_filled`
- `exit_target`
- `exit_stop`
- `exit_reassessment_open`
- `exit_forced_eod`
- `ambiguous_entry_exit_same_day`
- `ambiguous_stop_target_same_day`

## CLI examples

Default BTC-only setup:

```bash
PYTHONPATH=statistics python statistics/src/run_limit_order_backtest.py
```

Carry pending orders for up to 3 days:

```bash
PYTHONPATH=statistics python statistics/src/run_limit_order_backtest.py \
  --entry-ttl-days 3 \
  --pending-order-update-mode keep
```

Exit open positions at the next open when risk turns adverse:

```bash
PYTHONPATH=statistics python statistics/src/run_limit_order_backtest.py \
  --reassess-open-on-hard-risk-off \
  --reassess-open-on-rebound-lte-correction \
  --reassess-open-on-regime-break
```

Re-enable the older forced same-day close:

```bash
PYTHONPATH=statistics python statistics/src/run_limit_order_backtest.py \
  --force-eod-exit
```

Simple search:

```bash
PYTHONPATH=statistics python statistics/src/run_limit_order_backtest.py \
  --search \
  --grid-entry-offset-pct 0.01,0.015,0.02 \
  --grid-target-offset-pct 0.01,0.015,0.02 \
  --grid-stop-offset-pct 0.02,0.025,0.03 \
  --grid-max-band-pos 0.45,0.55 \
  --grid-min-hmm-conf 0.55,0.65
```

## Caveats

- This remains a daily-candle simulator, not an intraday execution replay.
- Same-day target recognition after an intraday entry remains path-ambiguous.
- `skip_ambiguous` is only fully meaningful for ambiguous same-day target
  recognition after intraday entry. When a position is already active from the
  session open and both stop and target are reachable, the state machine still
  needs a deterministic path, so it resolves conservatively while counting the ambiguity.
