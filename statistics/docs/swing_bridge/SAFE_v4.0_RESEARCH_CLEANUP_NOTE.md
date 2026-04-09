# SAFE v4.0 Research Cleanup Note

## What Was Moved

Research-stage work was split into purpose-specific folders:

- code:
  - `src/research/v4_iteration/core/indicator_audit/`
  - `src/research/v4_iteration/core/interaction_discovery/`
  - `src/research/v4_iteration/core/swing_detection/`
  - `src/research/v4_iteration/core/swing_bridge/`
- outputs:
  - `out/indicator_audit/`
  - `out/interaction_discovery/`
  - `out/swing_detection/`
  - `out/swing_bridge/`
- docs:
  - `docs/indicator_audit/`
  - `docs/interaction_discovery/`
  - `docs/swing_detection/`
  - `docs/swing_bridge/`

This keeps indicator audits, interaction discovery, swing extraction, and swing-bridge work from accumulating in one flat research surface.

## Why It Was Moved

- the research branch had become crowded enough that flat placement was obscuring intent
- swing work now has multiple layers: detector, sensitivity, live state, taxonomy, and condition mapping
- the new layout makes it clearer which files belong to:
  - indicator evidence gathering
  - interaction research
  - swing extraction and validation
  - indicator-to-swing bridge analysis

## What Changed In Swing Mapping Semantics

The previous swing-condition mapping mixed two different ideas:

- mapping a date to the confirmed swing that contains it
- mapping a date to the next confirmed swing after it

Those are now separated explicitly:

- `containing` mapping:
  - maps each date to the confirmed swing segment with `start_date <= date <= end_date`
  - used for early / mid / late swing-stage analysis
- `next` mapping:
  - maps each date to the first confirmed swing with `start_date > date`
  - used for predictive bridge analysis

This semantic split matters because a condition can be:

- informative about current swing maturity
- but weak as a predictor of the next swing

or the reverse.

The updated swing-bridge outputs now make that distinction explicit instead of combining both ideas under one ambiguous future-swing label.
