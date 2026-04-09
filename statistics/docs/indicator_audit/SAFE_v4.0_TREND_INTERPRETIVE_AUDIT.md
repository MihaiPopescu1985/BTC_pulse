# SAFE v4.0 Trend Interpretive Audit

## Scope
This audit covers only the current trend-family indicators in SAFE v4.0:

- `R_3`
- `R_7`
- `R_14`
- `TS_20`
- `TS_50`
- `TS_200`
- `LR_20`
- `LR_50`
- `LR_200`
- `ER_20`
- `ER_50`
- `ER_200`
- `RVR_20`
- `RVR_50`
- `RVR_200`

This is an interpretive audit, not a pruning pass. The purpose is to determine what each indicator is saying, where overlap is useful, where overlap is empty, and how future walk-forward iterations should use the existing information better.

## Repository context
All trend indicators are computed in [statistics/src/features/price_features.py](/home/mihai/Documents/BTC_pulse/statistics/src/features/price_features.py).

Current direct productive / validation usage:

- `TS_20`, `TS_50`, `TS_200`
  - [statistics/src/core/run_states.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/run_states.py)
  - [statistics/src/walkforward/run_decision_analysis_walkforward.py](/home/mihai/Documents/BTC_pulse/statistics/src/walkforward/run_decision_analysis_walkforward.py)
- `TS_50`, `ER_20`
  - [statistics/src/models/regime_hmm.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/regime_hmm.py)
  - [statistics/src/models/hazard_calibrated.py](/home/mihai/Documents/BTC_pulse/statistics/src/models/hazard_calibrated.py)
- `TS_50`
  - [statistics/src/core/exposure.py](/home/mihai/Documents/BTC_pulse/statistics/src/core/exposure.py)

Current descriptive / research usage:

- full trend family appears in:
  - [statistics/src/research/v4_iteration/research_archive/safe_interpreter.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/research_archive/safe_interpreter.py)
  - [statistics/src/research/v4_iteration/research_active/safe_interpreter_v2.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/research_active/safe_interpreter_v2.py)
- `TS_20`, `TS_50`, `TS_200` also appear in:
  - [statistics/src/research/v4_iteration/research_active/run_decision_analysis.py](/home/mihai/Documents/BTC_pulse/statistics/src/research/v4_iteration/research_active/run_decision_analysis.py)

## Reading principle
The correct question is not only “is this used now?” but:

- what market structure does this indicator express?
- does it express something distinct?
- does overlap help by adding confirmation, divergence, or narrative clarity?
- is the indicator likely stable enough to support future walk-forward refinement?

## Family overview

### 1. Recent impulse family
- `R_3`, `R_7`, `R_14`
- These describe speed and short-horizon travel.
- They are useful for answering:
  - how fast the market has moved recently
  - whether a move is fresh or already extended
  - whether a short pullback is happening inside a broader structure

### 2. Trend-strength backbone
- `TS_20`, `TS_50`, `TS_200`
- These are return signal-to-noise measures.
- They express whether directional drift is large relative to daily noise.
- This is the most operationally important trend family in the current productive path.

### 3. Geometric slope family
- `LR_20`, `LR_50`, `LR_200`
- These normalize the slope of a fitted line in log-price space by realized volatility.
- They tell a more shape-based story than `TS_*`.
- They are useful when the question is whether price is traveling in a clean geometric slope rather than simply posting a positive average return.

### 4. Path-cleanliness family
- `ER_20`, `ER_50`, `ER_200`
- These measure net travel divided by total path travel.
- They answer whether price movement is efficient or choppy.
- They are the best trend-family candidates for separating “trend” from “messy drift”.

### 5. Risk-adjusted drift alias family
- `RVR_20`, `RVR_50`, `RVR_200`
- Intended story: cumulative return normalized by realized volatility.
- In the current implementation, these are mathematically equivalent to the corresponding `TS_*` values up to a constant scale factor per horizon.
- That means the current overlap is not merely high. It is exact information duplication.

## Observed overlap patterns

Based on the current `features.csv`:

- `TS_20` vs `RVR_20`: correlation `1.00`
- `TS_50` vs `RVR_50`: correlation `1.00`
- `TS_200` vs `RVR_200`: correlation `1.00`
- `TS_20` vs `LR_20`: correlation about `0.92`
- `TS_50` vs `LR_50`: correlation about `0.93`
- `TS_200` vs `LR_200`: correlation about `0.93`
- `ER_*` has materially lower overlap with `TS_*` than `LR_*` does, which is useful
- `R_7` and `R_14` overlap meaningfully but not trivially; they describe momentum phase rather than persistence quality

Interpretation:

- `TS_*` and `LR_*` overlap in a useful way. They often agree in strong persistent trends, but they come from different intuitions:
  - `TS_*`: directional drift relative to return noise
  - `LR_*`: fitted slope relative to volatility
- `TS_*` and `ER_*` overlap in a useful way. Together they distinguish:
  - strong and clean trend
  - strong but noisy trend
  - weak and choppy drift
- `TS_*` and `RVR_*` do **not** currently overlap in a useful way. They are duplicated information in different labels.

## Direct usefulness observed in current evidence

Simple descriptive checks against `targets.csv` show:

- `ER_50` often has the strongest relationship within the trend family to:
  - `ret_10d`
  - `touch_up_2pct_10d`
  - `max_up_10d`
- `TS_20` and `TS_50` show modest but usable positive relation to upside outcomes
- `ER_20` is weaker than `ER_50` descriptively, but it is already productive because it helps the HMM and hazard layers detect path cleanliness
- `R_14` shows useful downside / swing sensitivity in several targets
- `R_3` is the noisiest of the recent-return group
- `RVR_*` contributes no distinct information beyond `TS_*` under the current implementation

This matters because the current accepted walk-forward edge is opportunity-led. That makes short-to-medium trend quality and directional cleanliness more relevant than raw downside filtering alone.

## Per-indicator audit

### `R_3`
- Measures:
  - 3-day log return.
- Market story:
  - freshest short impulse.
  - Useful for reading snapback, acceleration, or immediate extension.
- Overlap:
  - overlaps with `R_7`, `R_14`, and to a lesser extent `TS_20`.
- Overlap quality:
  - useful overlap, not empty. It expresses speed, not persistence.
- Current contribution:
  - not directly used in productive or accepted walk-forward logic.
  - used in research interpretation.
- Assessment:
  - noisy, fast, and fragile on its own.
  - still useful as contextual evidence for timing-sensitive opportunity logic.
- Classification:
  - `productive_context`
- Why:
  - helps tell whether a move is fresh or already spent, which is relevant for a time-sensitive edge.

### `R_7`
- Measures:
  - 7-day log return.
- Market story:
  - weekly swing direction.
  - bridges daily impulse and slower structure.
- Overlap:
  - overlaps with `R_3`, `R_14`, `LR_20`, and `TS_20`.
- Overlap quality:
  - useful overlap. This is a practical “recent swing” reference frame.
- Current contribution:
  - research / descriptive only.
- Assessment:
  - less noisy than `R_3`, still reactive enough to matter.
  - promising for pullback-inside-trend logic.
- Classification:
  - `productive_context`
- Why:
  - good candidate for future opportunity ranking refinement without being a core structural backbone.

### `R_14`
- Measures:
  - 14-day log return.
- Market story:
  - short swing context.
  - useful for reading whether the market has already traveled meaningfully before a new signal appears.
- Overlap:
  - overlaps with `R_7`, `LR_20`, `TS_20`.
- Overlap quality:
  - useful overlap. It is a bridge from raw move magnitude into short-trend structure.
- Current contribution:
  - research / descriptive only.
- Assessment:
  - more stable than `R_3`, often more interpretable than `R_7`.
  - potentially useful for distinguishing rebound setup from already-extended bounce.
- Classification:
  - `productive_context`
- Why:
  - strong contextual candidate for future state enrichment and extension control.

### `TS_20`
- Measures:
  - 20-day mean return divided by 20-day return volatility.
- Market story:
  - short-term directional pressure relative to noise.
- Overlap:
  - overlaps with `LR_20`, `ER_20`, `RVR_20`.
- Overlap quality:
  - useful with `LR_20` and `ER_20`
  - useless with `RVR_20` because `RVR_20` is a rescaled duplicate in the current implementation.
- Current contribution:
  - productive and accepted walk-forward logic.
- Assessment:
  - robust, interpretable, and clearly central.
  - one of the main “trend is supporting opportunity” features.
- Classification:
  - `productive_core`
- Why:
  - already part of the accepted walk-forward signal path and still tells a broad, useful story.

### `TS_50`
- Measures:
  - 50-day mean return divided by 50-day return volatility.
- Market story:
  - medium-term structure health.
- Overlap:
  - overlaps with `LR_50`, `ER_50`, `RVR_50`.
- Overlap quality:
  - useful with `LR_50` and `ER_50`
  - useless with `RVR_50` in the current implementation.
- Current contribution:
  - direct productive core:
    - HMM
    - hazard
    - exposure hard-risk-off logic
    - state definition
    - accepted walk-forward decision layer
- Assessment:
  - most central trend-family feature in the current repository.
  - robust, interpretable, and operationally important.
- Classification:
  - `productive_core`
- Why:
  - current SAFE already relies on it structurally, and the rationale is strong.

### `TS_200`
- Measures:
  - 200-day mean return divided by 200-day return volatility.
- Market story:
  - long-structure bias.
  - tells whether short opportunities are occurring within a favorable or unfavorable major backdrop.
- Overlap:
  - overlaps with `LR_200`, `ER_200`, `RVR_200`.
- Overlap quality:
  - useful with `LR_200` and `ER_200`
  - useless with `RVR_200` in the current implementation.
- Current contribution:
  - productive state and walk-forward context.
- Assessment:
  - slower and more lagging than `TS_20` / `TS_50`, but still important as structural context.
- Classification:
  - `productive_core`
- Why:
  - long-bias context matters for interpreting a time-sensitive opportunity signal.

### `LR_20`
- Measures:
  - 20-day normalized linear-regression slope of log price.
- Market story:
  - short trend geometry.
  - asks whether price is climbing in an orderly sloped path, not just posting positive average return.
- Overlap:
  - overlaps strongly with `TS_20`, also with `R_14`.
- Overlap quality:
  - useful overlap.
  - especially useful when it diverges from `TS_20`:
    - positive `TS_20`, weak `LR_20` can mean noisy advance
    - positive `LR_20`, weak `R_7` can mean underlying slope survived a short pause
- Current contribution:
  - research / descriptive only.
- Assessment:
  - promising for future walk-forward refinement.
  - more interpretable than a pure extra momentum window because it talks about shape.
- Classification:
  - `productive_context`
- Why:
  - it is not core today, but it expresses a distinct and plausible market story.

### `LR_50`
- Measures:
  - 50-day normalized linear-regression slope.
- Market story:
  - medium-horizon geometric slope.
- Overlap:
  - overlaps heavily with `TS_50`.
- Overlap quality:
  - still useful overlap, but less distinct than `LR_20`.
- Current contribution:
  - research / descriptive only.
- Assessment:
  - plausible contextual comparator to `TS_50`, but not obviously essential yet.
  - likely helpful mainly when testing confirmation/divergence versus `TS_50`.
- Classification:
  - `research_context`
- Why:
  - good comparison feature, but current evidence for distinct operational value is weaker than for `LR_20`.

### `LR_200`
- Measures:
  - 200-day normalized linear-regression slope.
- Market story:
  - long-horizon geometric slope.
- Overlap:
  - overlaps heavily with `TS_200`.
- Overlap quality:
  - useful mainly as a long-structure comparator, not a fast decision feature.
- Current contribution:
  - research / descriptive only.
- Assessment:
  - slow, lagging, and mainly explanatory.
  - can still help tell whether the long backdrop is gently sloped or only statistically positive.
- Classification:
  - `research_context`
- Why:
  - worthwhile as audit context, but not an obvious next-step productive addition.

### `ER_20`
- Measures:
  - 20-day directional efficiency ratio.
- Market story:
  - short-horizon trend cleanliness versus chop.
- Overlap:
  - overlaps with `TS_20`, but the story is different.
- Overlap quality:
  - very useful overlap.
  - `TS_20` answers “is there directional pressure?”
  - `ER_20` answers “is the path clean enough to trust?”
- Current contribution:
  - productive core in HMM and hazard.
- Assessment:
  - especially informative.
  - strong candidate for broader future walk-forward usage, not only model inputs.
- Classification:
  - `productive_core`
- Why:
  - it expresses something central to SAFE’s edge: whether the market is moving in a tradable way rather than in noisy churn.

### `ER_50`
- Measures:
  - 50-day directional efficiency ratio.
- Market story:
  - medium-horizon path cleanliness.
- Overlap:
  - overlaps with `TS_50`, but remains meaningfully distinct.
- Overlap quality:
  - useful overlap.
- Current contribution:
  - not directly productive today.
- Assessment:
  - one of the strongest non-core trend indicators in descriptive target checks.
  - especially promising for future opportunity ranking and “clean continuation versus messy drift” logic.
- Classification:
  - `productive_context`
- Why:
  - the current walk-forward layer likely underuses this information.

### `ER_200`
- Measures:
  - 200-day directional efficiency ratio.
- Market story:
  - long-horizon structural cleanliness.
- Overlap:
  - overlaps with `TS_200` and `LR_200`.
- Overlap quality:
  - useful but slower overlap.
- Current contribution:
  - research / descriptive only.
- Assessment:
  - more structural than tactical.
  - useful as a regime-conditioning comparator, less convincing as a direct short-horizon signal.
- Classification:
  - `research_context`
- Why:
  - informative for long backdrop interpretation, but not obviously necessary in the near-term decision layer.

### `RVR_20`
- Measures:
  - intended to be 20-day cumulative return normalized by realized volatility.
- Market story:
  - intended story is risk-adjusted drift.
- Overlap:
  - exact duplicate information of `TS_20` under the current implementation.
- Overlap quality:
  - useless overlap in its current mathematical form.
- Current contribution:
  - research lists / descriptive export only.
- Assessment:
  - suspect, not because the concept is bad, but because the current implementation adds no new information.
- Classification:
  - `suspect_or_misleading`
- Why:
  - the label suggests distinct information that is not actually present.

### `RVR_50`
- Measures:
  - intended medium-horizon risk-adjusted drift.
- Market story:
  - intended story is medium-horizon reward per unit volatility.
- Overlap:
  - exact duplicate information of `TS_50` under the current implementation.
- Overlap quality:
  - useless overlap.
- Current contribution:
  - descriptive only.
- Assessment:
  - suspect for the same reason as `RVR_20`.
- Classification:
  - `suspect_or_misleading`
- Why:
  - currently redundant in an empty way, not a useful way.

### `RVR_200`
- Measures:
  - intended long-horizon risk-adjusted drift.
- Market story:
  - intended story is long-horizon reward per unit volatility.
- Overlap:
  - exact duplicate information of `TS_200` under the current implementation.
- Overlap quality:
  - useless overlap.
- Current contribution:
  - descriptive only.
- Assessment:
  - suspect for the same reason as the shorter-horizon `RVR_*` measures.
- Classification:
  - `suspect_or_misleading`
- Why:
  - currently gives a new name without a new signal.

## Story-quality assessment

### Strongest current story-tellers
- `TS_50`
- `TS_20`
- `TS_200`
- `ER_20`
- `ER_50`

Why:
- together they describe direction, structural persistence, and path cleanliness
- that combination is well aligned with the validated SAFE conclusion that the edge is opportunity-led and time-sensitive

### Best contextual comparators
- `R_7`
- `R_14`
- `LR_20`
- `LR_50`
- `ER_200`

Why:
- they help describe whether trend is fresh, extended, geometric, or structurally clean
- they are good candidates for confirmation/divergence logic rather than stand-alone ranking drivers

### Weakest / most questionable
- `RVR_20`
- `RVR_50`
- `RVR_200`
- `R_3` as a stand-alone signal

Why:
- `RVR_*` is exact duplication in the current implementation
- `R_3` is useful context, but too fast and noisy to trust by itself

## Useful overlap vs useless overlap

### Useful overlap
- `TS_*` + `ER_*`
  - direction plus cleanliness
- `TS_*` + `LR_*`
  - statistical persistence plus geometric slope
- `R_*` + `TS_*`
  - recent impulse plus broader structure

### Useless overlap
- `TS_*` + `RVR_*`
  - same information under different labels in the current implementation

## Most promising indicators for future walk-forward refinement
- `ER_50`
- `LR_20`
- `R_14`
- `R_7`
- `ER_20` in a more explicit walk-forward role, not only inside HMM / hazard

Why these stand out:
- `ER_50` appears descriptively strong for medium-horizon upside / continuation behavior
- `LR_20` is a good candidate for shape confirmation
- `R_14` and `R_7` can help separate pullback opportunity from already-spent bounce
- `ER_20` likely improves tradability filtering by distinguishing clean continuation from noisy churn

## Trend-family guidance for future walk-forward iterations

### 1. Richer state descriptions
Current walk-forward logic uses `TS_20`, `TS_50`, `TS_200` directly. The next step should be richer trend states such as:

- short pullback inside medium constructive trend
- medium trend intact but path noisy
- long structure bearish but short rebound clean
- short impulse positive but medium structure weak

This requires using:
- `R_7`, `R_14`
- `TS_20`, `TS_50`, `TS_200`
- `ER_20`, `ER_50`
- optionally `LR_20`

### 2. Better opportunity ranking
The current walk-forward edge is opportunity-led. Trend-family refinement should therefore focus on ranking upside quality, not just filtering risk.

Most promising additions:
- stronger opportunity when `TS_20` and `TS_50` are supportive **and** `ER_20` or `ER_50` is high
- weaker opportunity when short returns are positive but `ER_20` is poor, indicating messy chase conditions

### 3. Confirmation / divergence logic
Some overlap is most useful when indicators disagree.

Examples:
- `TS_20` high, `ER_20` low:
  - move exists, but is noisy and less trustworthy
- `R_7` weak, `TS_50` positive:
  - short pullback inside intact structure
- `LR_20` positive, `R_3` negative:
  - slope intact, recent pause or dip

This is more valuable than treating each indicator as an isolated scalar.

### 4. Better asymmetry / context logic
Asymmetry added limited value in the first accepted walk-forward pass. Trend-family information can improve that by conditioning asymmetry on structure.

Examples:
- positive rebound signal matters more when `TS_50` is not broken and `ER_20` is improving
- downside danger matters more when `R_14` is already weak and `TS_200` is negative

### 5. Challenge empty aliases explicitly
`RVR_*` should remain available for audit context for now, but future productive use should treat them carefully.

Current recommendation:
- do not rely on `RVR_*` as distinct evidence until the implementation is intentionally differentiated or formally reduced to an alias

## Final classification summary

### Productive core
- `TS_20`
- `TS_50`
- `TS_200`
- `ER_20`

### Productive context
- `R_3`
- `R_7`
- `R_14`
- `LR_20`
- `ER_50`

### Research context
- `LR_50`
- `LR_200`
- `ER_200`

### Suspect or misleading
- `RVR_20`
- `RVR_50`
- `RVR_200`

## Bottom line
- The trend family is worth preserving.
- The current productive path is probably underusing trend cleanliness and short swing context.
- The strongest future refinement candidates are not more trend-strength aliases, but better use of:
  - `ER_50`
  - `LR_20`
  - `R_7`
  - `R_14`
  - explicit divergence between recent impulse and broader structure
- The only clearly problematic subgroup is `RVR_*`, because under the current implementation it does not tell a distinct story from `TS_*`.
