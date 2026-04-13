# SAFE v4.0 Repository Structure

## Purpose

SAFE v4.0 research is complete. The repository is now arranged around the retained productive research chain and the foundation needed for a future transition-detection iteration.

## Productive Chain

The retained runnable SAFE v4.0 chain now lives under:

- `src/research/v4_iteration/productive/`

This folder contains the scripts that reproduce the retained swing-bottom interpreter stack:

- reversal-zone dataset and corrected reversal-zone model outputs
- swing-extreme timing
- buy-side exploration and promoted buy-side hybrid source chain
- decision layer
- playbook layer
- strategy translation layer
- rule layer
- signal layer

These scripts are still research-stage, but they are the productive v4.0 chain. Dead-end validation, oracle feasibility, proxy, and intermediate refinement scripts were removed.

## Foundation Layer

Stable foundations remain under:

- `src/research/v4_iteration/core/swing_detection/`
- `src/research/v4_iteration/core/swing_bridge/`
- `src/research/v4_iteration/core/indicator_audit/`
- `src/research/v4_iteration/core/interaction_discovery/`

These support swing extraction, live swing state, swing taxonomy, indicator audit, and interaction discovery.

## Dashboard

The reusable dashboard remains under:

- `src/research/v4_iteration/dashboard/`

The dashboard registry now focuses on productive inspection views:

- `reversal_zone_dataset`
- `swing_extreme_timing`
- `buy_side_hybrid`
- `swing_decision_layer`
- `swing_playbook_layer`
- `strategy_translation_layer`
- `rule_layer`
- `signal_layer`

Exploration-only and superseded model views are no longer registered.

## Output Scope

Retained outputs remain under:

- `out/swing_bottom/`
- `out/swing_detection/`
- `out/swing_bridge/`

The retained `out/swing_bottom/` files correspond to the productive chain above. Removed outputs were validation-only, oracle-only, or dead-end research artifacts.

## Future Direction

The next iteration should not continue v4.0 threshold refinement. It should start a new transition-detection branch using the retained v4.0 stack as context and evaluation foundation.
