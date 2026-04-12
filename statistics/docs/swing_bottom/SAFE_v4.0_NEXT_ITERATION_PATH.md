# SAFE v4.0 Next Iteration Path

## Purpose

SAFE v4.0 should stop here as a research iteration. The stack is coherent enough to preserve, but the remaining blocker is not another threshold, filter, or minor model variation. The credible next iteration should focus on detecting the reversal transition itself.

The core lesson is simple: v4.0 can describe swing state well, but it does not causally identify the moment when a down swing is transitioning into a usable low with enough precision to make the oracle-like long subset deployable.

## What v4.0 Achieved

SAFE v4.0 built a usable structural research chain:

- Confirmed swing extraction and live causal swing-state features.
- Reversal-zone labels for good-enough low and high zones, not exact pivots.
- Leakage-safe reversal-zone modeling and timing scores.
- A validated buy-side timing reference and a usable sell-side timing reference.
- Decision, playbook, operational, rule, and signal layers that translate timing scores into structural interpretation.
- Event outcome analysis showing that `LONG_SIGNAL_NEW` has weak but real directional edge.
- Long-side refinement showing that the cleanest subset near the eventual swing low behaves much better than all long signals.
- Minimal long-only feasibility testing showing that the strict closest-to-low subset behaves like a viable strategy object as an oracle check.

This is enough to treat the v4.0 structure as a valid interpreter of swing conditions.

## What Blocked Deployment

The deployability blocker is the bottom-proximity condition.

The best long-side behavior depends on `high_closest_to_low`, which is tied to future-confirmed proximity to the actual swing low. That condition is useful as an oracle feasibility check, but it cannot be used as a causal strategy input.

The causal bottom-proximity proxy pass did not find a replacement strong enough to close the gap. Existing causal fields can identify broad long-side opportunity zones, but they do not reliably separate:

- early/noisy long contexts
- usable near-bottom contexts
- still-dangerous downside-continuation contexts

This means the current feature stack mostly describes state. It does not detect the reversal transition with enough precision.

Sell-side work should also remain secondary. Sell timing is useful as context, exit, veto, or risk-control information, but it did not show a clean standalone directional edge.

## Credible Future Iteration

The next credible iteration should be a transition-detection branch.

It should not ask, "is this state near a bottom?" using more static thresholds. It should ask, "is the market transitioning from downside continuation into downside failure, stabilization, and reversal?"

A useful next iteration would focus on causal transition evidence such as:

- Exhaustion to stabilization to reversal sequences.
- Volatility spike followed by compression or controlled range.
- Failure to make a new low after downside pressure.
- Higher low / failed breakdown structures using only information available at the time.
- Multi-candle reclaim behavior after local downside extension.
- Change-of-velocity or curvature features in returns, drawdown, range, and volatility.
- Downside momentum deceleration before upside confirmation.
- Local candle-sequence memory focused on transition, not generic analog similarity.
- Event-transition modeling from `LONG_SIGNAL_NEW` context into a better entry-quality state.

The modeling target should also change. Instead of another broad zone classifier, the next branch should model transition stages inside eligible long contexts:

- downside continuation likely
- stabilization forming
- reversal attempt active
- reversal confirmed enough for later strategy testing

This can still use the v4.0 swing and signal stack as the outer context, but the new features and objective should be transition-oriented.

## What Not To Repeat

A future iteration should probably not spend time on:

- More threshold tuning on the current causal bottom-proxy fields.
- More small variations of `buy_score`, `sell_score`, spread, clarity, and conflict filters.
- Repeating broad buy-side branch exploration over the same feature set.
- Treating the sell side as a primary standalone short-edge problem.
- Adding more layers above the current rule/signal stack before solving causal bottom proximity.
- Expanding strategy simulation around the oracle subset as if it were deployable.

The main blocker is not strategy plumbing. It is missing causal transition information.

## v4.0 Artifacts To Keep As Foundation

The following v4.0 artifacts remain conceptually valuable for a future iteration:

- Swing detection and live swing-state generation.
- Reversal-zone dataset and labels.
- Corrected leakage-safe reversal-zone modeling discipline.
- Swing-extreme timing outputs as broad structural context.
- Buy-side hybrid timing result as the best current buy context score.
- Sell-side timing score as an exit/veto/context input.
- Decision, playbook, operational, rule, and signal layers as the structural interpreter.
- Signal outcome evaluation, long refinement, final conditioning, and minimal strategy feasibility outputs as evidence of where the edge exists and why it is not yet causal.
- Causal bottom-proxy results as a negative result: the current causal stack is not enough to approximate the oracle condition.

These should be treated as foundation and evidence, not as a deployable strategy.

## Recommended Next Research Shape

The next iteration should start with a narrow transition dataset built around existing long signal contexts.

Recommended first question:

> Given a valid long-side structural context, can causal multi-day transition features identify whether downside pressure is failing and a usable low is forming?

Recommended initial scope:

- Use `LONG_SIGNAL_NEW` and nearby continuation days as the event universe.
- Build causal multi-day transition features from OHLC, volatility, drawdown, range, reclaim, and downside-failure behavior.
- Keep the oracle proximity labels only for evaluation, not as inputs.
- Evaluate by forward path cleanliness and proximity to the eventual low.
- Compare against the current v4.0 references: all `LONG_SIGNAL_NEW`, `LONG_QUALITY_HIGH`, and oracle `high_closest_to_low`.

The next iteration should be allowed to introduce new transition features, but it should not restart broad branch hunting.

## Stop Condition For v4.0

SAFE v4.0 should be considered complete as a structural interpreter and oracle feasibility study.

It should not be promoted as a deployable strategy because its best behavior still depends on future low proximity. The next meaningful improvement is not more filtering of the existing stack. It is a new causal transition-detection branch designed to approximate the missing bottom-proximity information at signal time.
