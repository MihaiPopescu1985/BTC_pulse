# SAFE Wrapper Reference Audit

## 1. Purpose

This is the updated non-destructive audit after compatibility wrappers were removed.

It answers one question:

> Are any old wrapper paths still required by active code, or are they now only historical documentation references?

This document records the post-removal state. It does not delete, archive, move, or rewrite any additional file.

## 2. Current Result

Current scan result:

- no active retained code imports any removed wrapper path
- no active research-only code imports any removed wrapper path
- removed wrapper paths are now referenced only in:
  - maintenance docs
  - generated historical artifacts such as `repomix-output.md`

So the removed wrapper set is no longer an active code dependency surface.

## 3. Classification Table

| Removed wrapper path | Replacement | References found | Reference type | Recommendation | Reason |
| --- | --- | --- | --- | --- | --- |
| `src/research/v4_iteration/core/swing_detection/run_swing_detection.py` | `src/foundation/swing_detection.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/core/swing_bridge/run_live_swing_state.py` | `src/foundation/live_swing_state.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/core/swing_bridge/run_swing_taxonomy.py` | `src/foundation/swing_taxonomy.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/core/swing_bridge/swing_bridge_common.py` | `src/foundation/swing_common.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/productive/run_reversal_zone_dataset.py` | `src/signals/reversal_zone_dataset.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/productive/run_reversal_zone_models.py` | `src/signals/reversal_zone_models.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/productive/run_swing_extreme_timing.py` | `src/signals/swing_extreme_timing.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/productive/run_buy_side_hybrid.py` | `src/signals/buy_side_hybrid.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/productive/run_swing_decision_layer.py` | `src/signals/swing_decision_layer.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/productive/run_swing_playbook_layer.py` | `src/signals/swing_playbook_layer.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/productive/run_strategy_translation_layer.py` | `src/signals/strategy_translation_layer.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/productive/run_rule_layer.py` | `src/signals/rule_layer.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/productive/run_signal_layer.py` | `src/signals/signal_layer.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/dashboard/run_dashboard.py` | `src/dashboard/run_dashboard.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/dashboard/dashboard_utils.py` | `src/dashboard/dashboard_utils.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |
| `src/research/v4_iteration/dashboard/view_registry.py` | `src/dashboard/view_registry.py` | `docs/SAFE_MODULE_MIGRATION_MAP.md`, `docs/SAFE_CLEANUP_INVENTORY.md`, this audit, `repomix-output.md` | `docs`, `historical artifact` | `keep_temporarily` | the file is removed, but maintenance docs still mention the old path |

## 4. Findings

### Active code references

None.

After import modernization, the previously identified research-only scripts now import:

- `src/foundation/`
- `src/signals/`

directly.

### Documentation references

The wrappers are still named in maintenance documents such as:

- `docs/SAFE_MODULE_MIGRATION_MAP.md`
- `docs/SAFE_CLEANUP_INVENTORY.md`
- `docs/SAFE_LAYER_CONTRACTS.md` for the old dashboard registry path
- this audit itself

These are not runtime dependencies. They only mean some maintenance docs still have historical path references to clean later.

### Historical artifact references

`repomix-output.md` still contains old commands, old imports, and path snapshots. That file is historical context, not active runtime usage.

## 5. Summary

### Total wrappers audited

- `16`

### Count by recommendation class

- `still_required`: `0`
- `keep_temporarily`: `16`
- `safe_candidate_for_removal_later`: `0`
- `review_needed`: `0`

### Wrappers with active code references

None.

### Safe candidates for later removal

None yet under the strict classification rule.

Reason:

- every wrapper is still named somewhere in current maintenance docs

### Removed wrappers still mentioned in docs

All audited wrapper paths are removed, but they still appear in maintenance docs:

- `src/research/v4_iteration/core/swing_detection/run_swing_detection.py`
- `src/research/v4_iteration/core/swing_bridge/run_live_swing_state.py`
- `src/research/v4_iteration/core/swing_bridge/run_swing_taxonomy.py`
- `src/research/v4_iteration/core/swing_bridge/swing_bridge_common.py`
- `src/research/v4_iteration/productive/run_reversal_zone_dataset.py`
- `src/research/v4_iteration/productive/run_reversal_zone_models.py`
- `src/research/v4_iteration/productive/run_swing_extreme_timing.py`
- `src/research/v4_iteration/productive/run_buy_side_hybrid.py`
- `src/research/v4_iteration/productive/run_swing_decision_layer.py`
- `src/research/v4_iteration/productive/run_swing_playbook_layer.py`
- `src/research/v4_iteration/productive/run_strategy_translation_layer.py`
- `src/research/v4_iteration/productive/run_rule_layer.py`
- `src/research/v4_iteration/productive/run_signal_layer.py`
- `src/research/v4_iteration/dashboard/run_dashboard.py`
- `src/research/v4_iteration/dashboard/dashboard_utils.py`
- `src/research/v4_iteration/dashboard/view_registry.py`

## 6. Recommended Next Cleanup Step

The next cleanup step is to clean maintenance-doc references that still mention removed wrapper paths. After that, this audit can be retired or reduced to a short historical note.
