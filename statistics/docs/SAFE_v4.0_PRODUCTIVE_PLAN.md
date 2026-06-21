# SAFE v4.0 Productive Plan

## A. Goal

Turn SAFE v4.0 from a validated research structure into a productive, maintainable signal engine.

The migration is complete. The repository structure is clean. The contracts pass. The next step is not another architecture change — it is running the stack regularly, auditing what the indicators actually contribute, and pruning what adds noise without adding signal.

This document defines the audit cycle and revalidation sequence needed to move from "researched and archived" to "actively used and maintained."

## B. Repository Structure After Migration

The productive path is entirely under:

```
statistics/src/
  foundation/     — swing structure (detection, live state, taxonomy)
  signals/        — 8-layer retained signal chain
  pipelines/      — orchestration (run_full_rebuild.py is the entry point)
  dashboard/      — local inspection
```

Supporting lower-level layers that need less frequent attention:

```
  core/           — BTC surface builders (features, HMM, hazard, targets, states)
  data/           — raw source loaders
  features/       — price feature logic
  models/         — HMM and hazard model logic
```

Research-only tools remain under `src/research/` and are not required for the default productive path.

See `docs/SAFE_v4.0_REPOSITORY_STRUCTURE.md` for the full runnable command reference.

## C. Indicator Audit Plan

The audit covers every feature family that feeds into the productive signal chain. Its goal is to classify each indicator into one of three classes:

- **productive_keep** — used, distinct, demonstrated contribution
- **research_only** — useful for exploration or diagnostics, not required for the productive chain
- **likely_remove** — redundant, untested in the current chain, or adding noise without contribution

### Price Feature Families (from `src/features/price_features.py`)

#### Candle group
`open`, `high`, `low`, `close`, `volume`, `candle_body`, `candle_range`, `body_to_range_ratio`, `upper_wick_ratio`, `lower_wick_ratio`, `close_in_range`

Baseline OHLCV inputs. Most downstream features depend on these, so they are not removable independently. The audit question for candle features is whether all four OHLC inputs are actually needed by the signal chain, or whether some features can fall back to close-only without loss.

#### Returns group
`r1`, `R_3`, `R_7`, `R_14`

Multi-horizon return features. `r1` is the core building block for almost every downstream feature. The remaining horizons (`R_3`, `R_7`, `R_14`) should be audited for whether they contribute distinctly to reversal zone or timing features beyond what `r1` already captures.

#### Trend group
`TS_20`, `TS_50`, `TS_200`, `LR_20`, `LR_50`, `LR_200`, `ER_20`, `ER_50`, `ER_200`, `RVR_20`, `RVR_50`, `RVR_200`

Twelve trend features across three horizons and four construction methods. The `notes` fields in the feature catalog already flag likely overlap: `LR_50` is "often redundant with TS_50 and RVR_50 in stable trends." The audit should confirm which horizon and construction combination the signal chain actually relies on and which are redundant.

#### Volatility group
`vol_20`, `true_range`, `atr`, `atr_pct`, `parkinson_vol`, `garman_klass_vol`, `ewma_vol`, `upside_semi_vol`, `downside_semi_vol`

Nine volatility features with significant overlap noted in the spec itself (`parkinson_vol` overlaps with `garman_klass_vol` and `atr`; `ewma_vol` overlaps with `vol_20`; `upside_semi_vol` and `downside_semi_vol` are useful when volatility is asymmetric). The audit should test whether the signal chain is sensitive to asymmetric volatility and whether multiple estimators are all needed.

#### Structure group
`band_hi`, `band_lo`, `band_w`, `band_pos`, `dist_from_mean_vol_units`

Rolling band position and stretch features. `band_pos` and `dist_from_mean_vol_units` are conceptually similar with different normalization. The audit should check which of these is actually selected by models in the reversal-zone or timing layers.

#### Path group
`switch_rate_50`, `run_length_up`, `run_length_down`, `run_magnitude_up`, `run_magnitude_down`, `return_accel`, `time_since_local_high`, `time_since_local_low`

Short-path memory features. `return_accel` is noted as "often noisy." Run-length pairs (`run_length_up`/`run_magnitude_up`) are conceptually paired. The audit should test which of these the signal chain actually uses at reversal-zone boundary conditions.

#### Volume group
`volume_log1p`, `relative_volume_20`, `volume_z`

Three volume normalizations with noted overlap (`relative_volume_20` and `volume_z` both measure participation anomaly). The audit should check whether either or both improve reversal-zone recall.

### On-Chain Feature Family (from `src/core/run_onchain_features.py`)

Currently produced on-chain features:

| Feature | Description |
| --- | --- |
| `ONCHAIN_AMOUNT_TOTAL` | Total BTC transaction volume (raw) |
| `ONCHAIN_AMOUNT_LOG` | Log-scaled total volume |
| `ONCHAIN_TX_WHALE` | Whale-bucket transaction count |
| `ONCHAIN_TX_MID` | Mid-bucket transaction count |
| `ONCHAIN_TX_SMALL` | Small-bucket transaction count |
| `ONCHAIN_WHALE_SHARE` | Whale share of total transactions |
| `ONCHAIN_DOMINANCE` | Large-participant dominance ratio |
| `ONCHAIN_VOL_Z` | Z-scored log volume vs history |
| `ONCHAIN_DOM_Z` | Z-scored log dominance vs history |
| `ONCHAIN_WHALE_SHARE_Z` | Z-scored whale share vs history |
| `ONCHAIN_AMOUNT_PCT` | Day-over-day pct change in total volume |
| `ONCHAIN_WHALE_TX_PCT` | Day-over-day pct change in whale count |
| `ONCHAIN_DOM_PCT` | Day-over-day pct change in dominance |

The on-chain family contributes participation and flow context. The audit should identify which of these the reversal-zone models or timing layers actually select and whether the z-scored and pct-change variants are both needed.

### Model Output Features

These are not raw features but computed model outputs that feed the signal chain:

| Feature | Source |
| --- | --- |
| HMM regime state / probabilities | `src/models/regime_hmm.py` |
| Hazard scores (calibrated) | `src/models/hazard_calibrated.py` |
| Targets | `src/core/run_targets.py` |
| States | `src/core/run_states.py` |
| Exposure | `src/core/run_exposure.py` |

The audit should confirm which regime states and hazard outputs are actually consumed by the reversal-zone dataset and whether any model outputs are assembled but never selected.

### Foundation / Swing State Features

These are structural features produced by `src/foundation/` and consumed directly by `src/signals/`:

| Feature | Source |
| --- | --- |
| Confirmed swing id and direction | `swing_detection.py` |
| Distance to current swing extreme (pct, range fraction) | `live_swing_state.py` |
| Row position relative to confirmed swing | `live_swing_state.py` |
| Swing taxonomy fields | `swing_taxonomy.py` |
| Reversal zone labels (buy/sell zone membership) | `reversal_zone_dataset.py` |

These are core structural inputs. The audit should verify that swing state features are being used causally (i.e., they are available at the time of the signal, not derived from future confirmed swing data).

## D. Audit Questions

For every indicator, the audit pass should ask:

1. **Does it add distinct information?** Is it measuring something the other features in the same family do not already capture?
2. **Is it redundant with another indicator?** Does correlation analysis or feature importance show it is a near-duplicate of another retained feature?
3. **Was it actually selected in the current signal chain?** Does the reversal-zone model or timing model actually include this feature as an input, or is it assembled into the feature surface but never used downstream?
4. **Does removing it degrade retained chain outputs?** After removing the feature and rebuilding the signal chain, do the reversal-zone scores, timing scores, decision states, or signal counts change materially?
5. **Is it only historically interesting, or actually useful?** Was this feature included because it was explored in an earlier iteration and never removed, or does it still serve a function in the current chain?

## E. Productive Subset Criteria

An indicator qualifies for **productive_keep** if it meets all of the following:

- **Distinct information**: its correlation with retained siblings is below a threshold that would flag it as a near-duplicate (suggested: Pearson or Spearman |r| < 0.85 with any other retained feature in the same family)
- **Chain selection**: it is either a direct model input in the reversal-zone or timing layer, or it feeds a retained model output that is selected
- **Non-degrading removal**: removing it and rebuilding does not push signal-layer or decision-layer state distributions outside the observed reference range
- **Interpretability**: its behavior at reversal-zone boundaries is explainable in structural terms (e.g., a price is near the lower band, volatility is compressing, on-chain participation is elevated)
- **Maintainability**: its source data is reliably available and its computation does not introduce data leakage risk

An indicator qualifies for **research_only** if it:

- Has interpretive or diagnostic value but is not selected by any retained model
- Requires expensive data or a non-default data pipeline
- Is useful only in future research branches (e.g., transition detection)

An indicator qualifies for **likely_remove** if it:

- Is highly correlated with a productive_keep sibling and offers no additional signal
- Was never actually selected by any model in the current chain
- Has notes in the feature spec flagging overlap without a demonstrated distinction

## F. Revalidation Order

After the audit and any feature pruning, the revalidation must run in this order to preserve the causal chain:

1. **Indicator audit** — complete the classification table; identify features for pruning
2. **Feature pruning / classification** — remove or mark likely_remove features in `src/features/price_features.py` and `src/core/run_onchain_features.py`
3. **Rebuild BTC feature surface** — `python src/core/run_features.py` and `python src/core/run_onchain_features.py`
4. **Rebuild models if needed** — rerun HMM and hazard training only if feature changes affect their inputs
5. **Rebuild foundation** — `python src/pipelines/run_foundation_pipeline.py`
6. **Rebuild signal chain** — `python src/pipelines/run_signal_pipeline.py`
7. **Validate contracts** — `python src/pipelines/run_validation.py`
8. **Inspect dashboard outputs** — `python src/dashboard/run_dashboard.py` to confirm retained views look structurally consistent with pre-pruning reference outputs
9. **Re-lock productive v4.0** — update this document with audit results; tag the confirmed productive feature set

If step 8 shows material divergence from the reference outputs, treat it as a regression signal and investigate before treating the pruned set as productive.

## G. Non-Goals

This audit phase is not:

- **Not a new model family effort.** The HMM and hazard models stay as-is unless audit findings directly implicate a model input that must change.
- **Not a broad optimization sweep.** Hyperparameter tuning, threshold searching, or alternative model comparisons are out of scope.
- **Not a strategy redesign.** Signal layer outputs are interpreted structurally. PnL simulation and position sizing are not part of this cycle.
- **Not a transition-detection research branch.** That is a separate future iteration described in `docs/swing_bottom/SAFE_v4.0_NEXT_ITERATION_PATH.md`.
- **Not a data source expansion.** Adding new data sources (funding rates, open interest, ETF flows, etc.) is deferred until the current feature surface is audited and stabilized.

## H. First Practical Step

Before running the full audit, run the retained pipeline end-to-end and confirm the current outputs are consistent with the last known-good reference:

```bash
cd statistics
python src/pipelines/run_full_rebuild.py
python src/dashboard/run_dashboard.py --check
```

If both complete without errors, the stack is in a known-good state and the audit can begin from a clean baseline.
