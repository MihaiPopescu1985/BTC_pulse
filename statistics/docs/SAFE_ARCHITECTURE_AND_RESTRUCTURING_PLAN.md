# SAFE Architecture And Restructuring Plan

## 1. Why The Repository Is Being Reorganized

SAFE v4.0 produced a coherent market-structure interpreter, but the repository still reflects the path used to discover it. Productive foundation code, retained signal-chain code, exploratory research artifacts, and iteration-specific scripts are still too close together.

The main problems are:

- Productive foundation and research artifacts are still mixed in the same high-level areas.
- Some file boundaries reflect iteration history rather than stable responsibility.
- Too many intermediate outputs can look like default outputs even when they are diagnostic or exploratory.
- The retained signal chain is not yet obvious enough as the main downstream domain.
- Future data-source additions would become risky if raw source logic leaks into signal/rule/playbook code.

The reorganization should make the retained SAFE stack easier to run, inspect, extend, and refactor without reopening old research branches.

## 2. Architectural Principle

SAFE should be organized around stable responsibilities at the top level, not around version numbers, temporary research passes, or single pipeline scripts.

The target architecture should enforce these principles:

- Top-level code domains should represent durable responsibilities.
- Downstream layers should consume normalized causal features, not raw source files.
- Stable contracts between layers matter more than the exact file names.
- The retained signal stack should be a first-class domain.
- Research should be isolated from default productive paths and run only when intentionally selected.

The central invariant is:

> Downstream signal logic consumes features and structure contracts, not raw data sources.

This is what keeps new data-source integration local and prevents the signal stack from becoming source-specific.

## 3. Proposed Top-Level Code Domains

The target code layout should move toward responsibility-centered domains like this:

```text
src/
  data/
  features/
  models/
  foundation/
  signals/
  pipelines/
  research/
  dashboard/
  util/
```

The exact names can still be adjusted during implementation, but the responsibilities should stay stable.

### `data/`

Owns raw data access and source adapters.

Belongs here:

- raw source loaders
- source schemas and validation
- date parsing and alignment checks at the source boundary
- source-specific cleaning that is required before feature construction

Does not belong here:

- signal logic
- swing-state logic
- model scoring
- research-specific joins

Neighboring layer:

- feeds cleaned source frames into `features/`

### `features/`

Owns normalized causal feature construction.

Belongs here:

- price feature builders
- on-chain feature builders
- future funding/open-interest/options/macro/stablecoin feature builders
- merged feature-surface assembly
- feature contract validation

Does not belong here:

- raw source file assumptions beyond loader outputs
- swing labels or future-derived targets
- decision/playbook/rule logic

Neighboring layer:

- consumes `data/` outputs and produces the normalized causal feature surface used by `foundation/`, `models/`, and `signals/`

### `models/`

Owns reusable predictive model training/scoring that is not specific to one research experiment.

Belongs here:

- HMM/regime model code
- hazard model code
- reusable model serialization/loading helpers
- stable model contracts

Does not belong here:

- branch-specific research comparisons
- one-off experiment reports
- signal state machines

Neighboring layer:

- consumes feature contracts and exports model outputs as causal fields

### `foundation/`

Owns reusable market-structure foundations.

Belongs here:

- swing detection
- live swing state
- swing taxonomy
- swing/structure mapping helpers
- indicator audit logic if kept as reusable foundation
- interaction discovery only if it remains a stable foundation input

Does not belong here:

- branch-specific entry experiments
- playbook/rule/signal state machines
- strategy feasibility checks

Neighboring layer:

- consumes feature/model outputs and provides structure contracts to `signals/`

### `signals/`

Owns the retained SAFE signal stack as a first-class domain.

Belongs here:

- reversal-zone dataset/model logic that is part of the retained foundation for signals
- swing-extreme timing
- promoted buy-side hybrid reference
- decision layer
- playbook layer
- operational/strategy-translation layer
- rule layer
- signal realization layer

Does not belong here:

- broad exploration sprints
- proxy dead ends
- oracle-only feasibility checks
- PnL backtests
- raw data loading

Neighboring layer:

- consumes `features/`, `models/`, and `foundation/` contracts; produces signal-facing outputs for `pipelines/` and `dashboard/`

### `pipelines/`

Owns runnable orchestration.

Belongs here:

- default end-to-end pipeline entrypoints
- reproducibility runners
- small command wrappers that run the retained chain in order
- validation commands for default outputs

Does not belong here:

- reusable feature/model/foundation logic
- research branch internals
- dashboard UI code

Neighboring layer:

- orchestrates `data/`, `features/`, `models/`, `foundation/`, and `signals/`

### `research/`

Owns opt-in experiments.

Belongs here:

- future transition-detection branch experiments
- alternative target definitions
- proxy experiments
- evaluation passes not part of the retained default chain
- exploratory comparison tables

Does not belong here:

- default productive signal stack
- reusable foundation logic after it has graduated
- dashboard core

Neighboring layer:

- can consume default contracts, but should not be required by productive pipeline runs

### `dashboard/` Or `apps/`

Owns human-facing inspection tools.

Belongs here:

- reusable local research dashboard
- view registry
- static dashboard assets
- optional future lightweight apps

Does not belong here:

- per-script visualization forks
- model training
- signal generation logic

Neighboring layer:

- consumes registered CSV outputs and price data for inspection

## 4. Stable Contracts Between Layers

Each retained layer should have an explicit input/output contract. Contracts are more important than exact file names because they allow files to move and implementations to change without breaking downstream logic.

### Normalized Feature Surface Contract

Purpose:

- one row per date
- causal fields only
- stable column naming
- no raw source-specific assumptions in downstream consumers

Typical outputs:

- `features.csv`
- `onchain_features.csv`
- future merged or source-specific feature surfaces

Contract requirements:

- no duplicate dates
- deterministic sorting
- explicit missing-value policy
- feature columns are causal at the row date

### Swing / Structure Foundation Contract

Purpose:

- provide confirmed swings, live swing state, and swing taxonomy in stable shapes

Typical outputs:

- `swings.csv`
- `live_swing_state.csv`
- `swing_taxonomy.csv`
- `swing_condition_mapping.csv`

Contract requirements:

- confirmed-swing metadata is clearly separated from live causal state
- future-derived labels are never mixed into causal feature inputs
- containing-swing and next-swing semantics remain separate

### Retained Signal Stack Contract

Purpose:

- turn timing and structure into interpretable downstream states

Retained layers:

- timing
- decision
- playbook
- operational / strategy translation
- rule
- signal

Contract requirements:

- one row per date for daily state outputs
- explicit score columns
- explicit categorical state columns
- explicit label/evaluation columns when present
- stable dashboard-compatible CSV exports

### Human-Facing Output Contract

Purpose:

- make the retained state easy to inspect without reading intermediate research files

Typical outputs:

- dashboard-registered daily CSVs
- compact layer summary CSVs
- markdown reports for retained layers

Contract requirements:

- dashboard-compatible `date` column
- clear score/label/diagnostic fields
- no exploratory comparison outputs in the default view set

## 5. Future Data-Source Extensibility

New data sources should enter through source adapters and normalized feature-ingestion boundaries.

Future sources might include:

- funding
- open interest
- options
- ETF flows
- macro
- stablecoin flows
- miner data
- exchange reserves

The integration rule is:

1. Add a source loader or adapter under `data/`.
2. Validate and date-align source-specific data at the boundary.
3. Convert the source into causal normalized features under `features/`.
4. Register or merge those fields into the feature surface contract.
5. Expose selected features to foundation/signals/research only through the normalized feature surface.

Downstream signal logic should not read raw source files directly. A new source should not require editing decision, playbook, rule, or signal code unless a deliberate new feature contract is being consumed.

This keeps data-source growth local and prevents source-specific logic from spreading through the repository.

## 6. Retained Signal Chain

The retained signal chain should become a first-class domain because it is the keeper downstream path from v4.0.

The retained chain is:

```text
reversal-zone labels / model foundation
  -> swing-extreme timing
  -> promoted buy-side hybrid timing
  -> decision layer
  -> playbook layer
  -> operational translation layer
  -> rule layer
  -> signal layer
```

Its purpose is not to be a production trading engine. Its purpose is to provide the current structural interpretation of the market:

- where swing-low and swing-high timing pressure appears
- whether buy or sell timing dominates
- whether the state is clear, conflicted, neutral, or blocked
- whether a structural signal event has appeared

Sell-side timing should remain primarily:

- exit context
- veto context
- risk/de-risk context

It should not be treated as a standalone short-edge engine unless a future iteration proves otherwise.

## 7. Research Isolation

Research should be opt-in and should not be part of default productive runs.

Belongs in research:

- branch experiments
- transition-detection experiments
- proxy experiments
- alternative objectives
- evaluation-only passes
- comparison tables and exploratory reports

Research outputs should be clearly separated from default outputs. If a research artifact graduates, it should be moved into the appropriate stable domain and given a contract. Until then, it should not appear as a default pipeline output or dashboard default view.

The next credible research branch is transition detection, not more v4.0 threshold filtering.

## 8. Output Policy

Default outputs should be limited to files that matter operationally or structurally.

Default output groups should include:

- productive feature surfaces
- model packs and stable model outputs
- swing/structure foundation outputs
- retained signal-facing daily outputs
- compact summaries for retained layers
- dashboard-registered inspection views

Exploratory outputs should not live beside default outputs indefinitely. Comparison tables, validation sweeps, oracle feasibility checks, and dead-end proxy results should be generated only in opt-in research paths and removed or isolated after conclusions are captured.

The dashboard should focus on retained, date-aligned views. Event-level or comparison-only outputs should not be dashboard defaults unless they become operational inspection artifacts.

## 9. File-Boundary Guidance

Folder moves alone are not enough. File boundaries should match responsibilities.

Merge files when:

- several tiny scripts exist only because of iteration history
- one conceptual layer is split across temporary experiment files
- boundaries add ceremony without improving reuse or clarity

Split files when:

- orchestration, reusable logic, evaluation, and markdown rendering are mixed too tightly
- one module contains both stable logic and experiment-specific reporting
- a helper is reused by multiple retained layers

Avoid:

- tiny one-off modules in the retained default chain
- experiment-specific reporting mixed into reusable layer logic
- raw source assumptions inside signal modules
- hidden feature selection or leakage rules spread across many files

Prefer:

- stable contracts
- explicit validation
- deterministic exports
- simple runnable entrypoints
- dashboard-compatible retained outputs

## 10. Proposed Restructuring Sequence

Restructuring should proceed in small controlled steps.

1. Finalize this architecture document.
2. Define explicit contracts for feature surface, swing foundation, signal stack, and dashboard outputs.
3. Move or relabel domains and directories to match stable responsibilities.
4. Split or merge files where boundaries reflect iteration history rather than responsibility.
5. Update imports and runnable entrypoints.
6. Run compile checks and dashboard validation after each move.
7. Simplify default outputs and dashboard registry to retained signal-facing views.
8. Move exploratory research into opt-in branches.
9. Only then remove or archive obsolete artifacts.

Each step should preserve behavior unless a change is explicitly part of the restructuring plan. The goal is not to re-research SAFE v4.0. The goal is to make the retained interpreter chain maintainable, extensible, and ready to support a future transition-detection iteration.
