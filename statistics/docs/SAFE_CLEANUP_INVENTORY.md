# SAFE Cleanup Inventory

## 1. Purpose

This is a non-destructive cleanup classification document.

It records what is currently retained, what has already been removed as compatibility-only scaffolding, and what remains research-only or optional.

It does not delete, archive, move, or rewrite any files.

## 2. Retained Migrated Domains

The current retained domains are:

- `src/foundation/`
  - retained swing-structure foundation logic
  - owns default foundation rebuild entrypoints
- `src/signals/`
  - retained signal chain
  - owns retained signal-producing logic and retained downstream state layers
- `src/dashboard/`
  - retained human-facing inspection runtime
  - owns the dashboard registry and static UI asset
- `src/pipelines/`
  - retained orchestration layer
  - owns clean top-level rebuild and validation commands
- `src/contracts/`
  - retained validation guardrails for now
  - owns CSV/dashboard contract definitions and check runners

## 3. Removed Compatibility Wrappers
These wrapper files have already been removed.

Their old paths now matter only as historical references that may still appear in maintenance docs or generated historical artifacts.

### Former Core Swing Detection / Bridge Wrappers

| Removed path | Replacement | Status | Reason |
| --- | --- | --- | --- |
| `src/research/v4_iteration/core/swing_detection/run_swing_detection.py` | `src/foundation/swing_detection.py` | `removed` | old wrapper removed after research imports and operational workflows were switched |
| `src/research/v4_iteration/core/swing_bridge/run_live_swing_state.py` | `src/foundation/live_swing_state.py` | `removed` | old wrapper removed after research imports and operational workflows were switched |
| `src/research/v4_iteration/core/swing_bridge/run_swing_taxonomy.py` | `src/foundation/swing_taxonomy.py` | `removed` | old wrapper removed after operational workflows were switched |
| `src/research/v4_iteration/core/swing_bridge/swing_bridge_common.py` | `src/foundation/swing_common.py` | `removed` | old wrapper removed after research imports were switched |

### Former Productive Signal Wrappers

| Removed path | Replacement | Status | Reason |
| --- | --- | --- | --- |
| `src/research/v4_iteration/productive/run_reversal_zone_dataset.py` | `src/signals/reversal_zone_dataset.py` | `removed` | old wrapper removed after retained pipelines and research imports stopped depending on it |
| `src/research/v4_iteration/productive/run_reversal_zone_models.py` | `src/signals/reversal_zone_models.py` | `removed` | old wrapper removed after retained pipelines and research imports stopped depending on it |
| `src/research/v4_iteration/productive/run_swing_extreme_timing.py` | `src/signals/swing_extreme_timing.py` | `removed` | old wrapper removed after retained pipelines and research imports stopped depending on it |
| `src/research/v4_iteration/productive/run_buy_side_hybrid.py` | `src/signals/buy_side_hybrid.py` | `removed` | old wrapper removed after retained workflows switched to `src/signals/` |
| `src/research/v4_iteration/productive/run_swing_decision_layer.py` | `src/signals/swing_decision_layer.py` | `removed` | old wrapper removed after retained workflows switched to `src/signals/` |
| `src/research/v4_iteration/productive/run_swing_playbook_layer.py` | `src/signals/swing_playbook_layer.py` | `removed` | old wrapper removed after retained workflows switched to `src/signals/` |
| `src/research/v4_iteration/productive/run_strategy_translation_layer.py` | `src/signals/strategy_translation_layer.py` | `removed` | old wrapper removed after retained workflows switched to `src/signals/` |
| `src/research/v4_iteration/productive/run_rule_layer.py` | `src/signals/rule_layer.py` | `removed` | old wrapper removed after retained workflows switched to `src/signals/` |
| `src/research/v4_iteration/productive/run_signal_layer.py` | `src/signals/signal_layer.py` | `removed` | old wrapper removed after retained workflows switched to `src/signals/` |

### Former Dashboard Wrappers

| Removed path | Replacement | Status | Reason |
| --- | --- | --- | --- |
| `src/research/v4_iteration/dashboard/run_dashboard.py` | `src/dashboard/run_dashboard.py` | `removed` | old dashboard wrapper removed after operational docs switched to `src/dashboard/` |
| `src/research/v4_iteration/dashboard/dashboard_utils.py` | `src/dashboard/dashboard_utils.py` | `removed` | old dashboard helper wrapper removed after runtime imports switched to `src/dashboard/` |
| `src/research/v4_iteration/dashboard/view_registry.py` | `src/dashboard/view_registry.py` | `removed` | old dashboard registry wrapper removed after runtime imports switched to `src/dashboard/` |

Current note:

- any remaining old wrapper-path references in docs should be treated as maintenance cleanup items, not as current repository entrypoints

## 4. Research-Only Scripts Inventory

These files are not part of the retained default chain even if some remain useful for analysis or future cleanup decisions.

| Path | Classification | Notes |
| --- | --- | --- |
| `src/research/v4_iteration/core/swing_detection/run_swing_sensitivity.py` | `research_keep` | useful swing-granularity diagnostic; not default runtime |
| `src/research/v4_iteration/core/swing_bridge/run_swing_condition_mapping.py` | `research_keep` | interpretive mapping output; optional by architecture |
| `src/research/v4_iteration/core/indicator_audit/run_indicator_reliability.py` | `research_keep` | retained audit research, not default runtime |
| `src/research/v4_iteration/core/interaction_discovery/run_interaction_discovery.py` | `research_keep` | retained discovery research, not default runtime |
| `src/research/v4_iteration/core/interaction_discovery/trend_state_v1.py` | `review_needed` | exploratory helper/experiment; likely not part of retained operational path |
| `src/research/v4_iteration/productive/run_buy_side_exploration.py` | `research_keep` | broad exploration/reporting remains research-shaped after hybrid extraction |
| `src/research/v4_iteration/productive/run_bottom_dataset.py` | `review_needed` | legacy bottom-dataset CLI; some helper logic was already extracted to `src/signals/reversal_zone_common.py` |

Wrapper files are intentionally excluded from this section because they are compatibility shims, not active research logic.

## 5. Retained Default Outputs

These outputs should be treated as default retained outputs for the current architecture.

### Feature / Model Surfaces

- `out/features.csv`
- `out/onchain_features.csv`
- `out/models/hmm_pack.joblib`
- `out/models/hazard_pack.joblib`

### Foundation Outputs

- `out/swing_detection/swings.csv`
- `out/swing_bridge/live_swing_state.csv`
- `out/swing_bridge/swing_taxonomy.csv`

### Retained Signal Outputs

- `out/swing_bottom/reversal_zone_dataset.csv`
- `out/swing_bottom/swing_extreme_timing.csv`
- `out/swing_bottom/buy_side_hybrid_scores.csv`
- `out/swing_bottom/swing_decision_layer.csv`
- `out/swing_bottom/swing_playbook_layer.csv`
- `out/swing_bottom/strategy_translation_layer.csv`
- `out/swing_bottom/rule_layer.csv`
- `out/swing_bottom/signal_layer.csv`

### Dashboard-Registered Retained Outputs

The retained dashboard currently treats these as default registered views:

- `out/swing_bottom/reversal_zone_dataset.csv`
- `out/swing_bottom/swing_extreme_timing.csv`
- `out/swing_bottom/buy_side_hybrid_scores.csv`
- `out/swing_bottom/swing_decision_layer.csv`
- `out/swing_bottom/swing_playbook_layer.csv`
- `out/swing_bottom/strategy_translation_layer.csv`
- `out/swing_bottom/rule_layer.csv`
- `out/swing_bottom/signal_layer.csv`

Default note:

- these are the practical retained surfaces that the new pipelines rebuild, the retained contracts validate, or the retained dashboard registers directly

## 6. Research-Only / Optional Outputs

These outputs are useful diagnostically or historically, but should not be treated as required default runtime outputs.

### Optional Foundation / Structure Outputs

- `out/swing_detection/swing_sensitivity_summary.csv`
- `out/swing_bridge/swing_condition_mapping.csv`

### Research / Comparison / Diagnostic Signal Outputs

- `out/swing_bottom/reversal_zone_predictions.csv`
- `out/swing_bottom/reversal_zone_metrics.csv`
- `out/swing_bottom/buy_side_hybrid_comparison.csv`
- `out/swing_bottom/buy_side_hybrid_swing_summary.csv`
- `out/swing_bottom/swing_extreme_timing_ablation.csv`
- `out/swing_bottom/swing_extreme_timing_swing_summary.csv`
- `out/swing_bottom/swing_extreme_timing_thresholds.csv`
- `out/swing_bottom/swing_decision_layer_summary.csv`
- `out/swing_bottom/swing_playbook_layer_summary.csv`
- `out/swing_bottom/strategy_translation_summary.csv`
- `out/swing_bottom/rule_layer_summary.csv`
- `out/swing_bottom/signal_layer_summary.csv`

These are not bad outputs. They are just not the minimal retained operational surface.

## 7. Documentation Cleanup Inventory

### Current Operational Docs

- `docs/HowTo.md`
- `docs/SAFE_v4.0_REPRODUCIBILITY.md`
- `docs/swing_bottom/SAFE_v4.0_DASHBOARD.md`

Operational-note:

- these are still useful for running the repository today, but `HowTo.md` still contains pre-migration structure language and should later be rewritten around `src/foundation/`, `src/signals/`, `src/dashboard/`, and `src/pipelines/`

### Architecture / Restructuring Docs

- `docs/SAFE_ARCHITECTURE_AND_RESTRUCTURING_PLAN.md`
- `docs/SAFE_LAYER_CONTRACTS.md`
- `docs/SAFE_MODULE_MIGRATION_MAP.md`
- `docs/SAFE_v4.0_REPOSITORY_STRUCTURE.md`
- `docs/CLEANUP_SUMMARY.md`

Later note:

- these should eventually be rewritten into clean current-state design/workflow documents rather than retaining migration-history narrative

### Retained Research Foundation Docs

- `docs/swing_bridge/SAFE_v4.0_LIVE_SWING_STATE.md`
- `docs/swing_bridge/SAFE_v4.0_SWING_TAXONOMY.md`
- `docs/swing_detection/SAFE_v4.0_SWING_DISTRIBUTION.md`
- `docs/indicator_audit/*`

### Historical / Research-Result Docs Still Present

- `docs/swing_bottom/SAFE_v4.0_REVERSAL_ZONE_DATASET.md`
- `docs/swing_bottom/SAFE_v4.0_REVERSAL_ZONE_MODELS.md`
- `docs/swing_bottom/SAFE_v4.0_SWING_EXTREME_TIMING.md`
- `docs/swing_bottom/SAFE_v4.0_BUY_SIDE_EXPLORATION.md`
- `docs/swing_bottom/SAFE_v4.0_BUY_SIDE_HYBRID.md`
- `docs/swing_bottom/SAFE_v4.0_SWING_DECISION_LAYER.md`
- `docs/swing_bottom/SAFE_v4.0_SWING_PLAYBOOK_LAYER.md`
- `docs/swing_bottom/SAFE_v4.0_STRATEGY_TRANSLATION_LAYER.md`
- `docs/swing_bottom/SAFE_v4.0_RULE_LAYER.md`
- `docs/swing_bottom/SAFE_v4.0_SIGNAL_LAYER.md`
- `docs/swing_bottom/SAFE_v4.0_NEXT_ITERATION_PATH.md`
- `docs/swing_detection/SAFE_v4.0_SWING_DASHBOARD_OVERLAY.md`
- `docs/swing_detection/SAFE_v4.0_SWING_SENSITIVITY.md`
- `docs/swing_bridge/SAFE_v4.0_SWING_CONDITION_MAPPING.md`

### Candidates For Later Rewrite Or Archive

- architecture/restructuring documents after the migration stabilizes
- `docs/HowTo.md` after a clean current-workflow replacement exists
- historical swing-bottom result docs that are useful as research records but not as operational documentation
- swing-condition mapping and swing-sensitivity docs if those outputs remain optional research-only artifacts

## 8. Recommended Cleanup Sequence

Recommended order for the next destructive/archival cleanup phase:

1. switch operational docs and day-to-day workflows to `src/pipelines/` and new top-level domain commands only
2. keep compatibility wrappers temporarily while command references are still transitioning
3. mark research-only scripts and outputs clearly in docs and, if useful, with small directory-level notes
4. keep the dashboard registry limited to retained date-aligned views and do not reintroduce research-only artifacts into the default inspection surface
5. remove compatibility wrappers only after old research-path commands are no longer referenced
6. review research-only scripts:
   - keep actively useful ones
   - archive later for dormant experiments
   - simplify legacy helper-bearing scripts whose reusable logic already migrated
7. rewrite architecture/restructuring docs into clean current design/workflow/extension documentation with no migration-history emphasis

This sequence is recommended only. It is not executed by this inventory step.
