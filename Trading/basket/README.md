# Basket Mean-Reversion Scoring (Python)

This project is a config-driven research and analytics module for scoring price time series based on event-driven mean reversion behavior. It is designed to run efficiently across large universes of symbols (tens of thousands of charts) and to remain easy to extend as the analytics become more advanced.

## What it does
Given a price series, the tool:
- Estimates a reference mean (e.g., rolling SMA) and volatility (e.g., EWMA).
- Detects deviation events when price moves a statistically meaningful distance from the mean (typically via a volatility-normalized threshold, e.g., z-score).
- Tracks each event until it reverts back toward the mean (within a configurable tolerance) or fails (timeout, excessive excursion, or other criteria).
- Produces a mean-reversion score expressed as a percentage:
  - `reversion_rate = reverted_events / total_events`
- Optionally produces directional and regime-aware breakdowns (upside vs downside deviations, volatility buckets) plus per-event diagnostics.

## Why "event-driven" matters
Instead of counting "how many bars are above/below a threshold," the tool models complete deviation episodes with explicit lifecycle states (start -> active -> resolved). This avoids double-counting long excursions and makes the score interpretable and comparable across assets and regimes.

## Core design goals
- Causal by construction (no look-ahead bias): all estimators and decisions at time t depend only on data <= t.
- Configuration is the contract: behavior is fully defined in `config.yaml` and validated with Pydantic.
- Composition root wiring: concrete implementations are selected and instantiated in one place (`composition_root.py`), keeping the engine free of configuration and wiring concerns.
- Batch-friendly performance: the architecture is intended for single-pass evaluation per series and straightforward multiprocessing at the asset level.

## High-level architecture
- Config layer:
  - `config.yaml` (runtime behavior)
  - Pydantic config models (strict validation, typed params)
- Composition root:
  - Constructs concrete components (mean, vol, detector, criteria) from the validated config.
- Core engine (to be implemented next):
  - Iterates over the series once, manages one active event by default, produces results and diagnostics.
- Components (implementations):
  - Mean estimator(s), volatility estimator(s), deviation detectors, reversion criteria, and failure criteria.

## Intended use cases
- Screening and ranking symbols by mean-reversion tendency under consistent definitions.
- Comparing the stability of mean reversion across volatility regimes and parameter sets.
- Supporting pairs/basket workflows where "reversion reliability" is a key filter before deeper modeling.

## Non-goals (for now)
- Trade simulation / PnL attribution
- Portfolio construction and execution
- Fully automatic external plugin discovery

These can be layered on later without changing the fundamentals of the event model and configuration contract.

## Configuration (`config.yaml`)

This project is fully configuration-driven. All runtime behavior must be expressed in `config.yaml` and is validated via Pydantic models (unknown keys are rejected, types are enforced, and invalid combinations fail fast at startup).

### Overview

A valid `config.yaml` has these top-level sections:
- `config_version`: Configuration schema version (currently `1`)
- `engine`: Global engine behavior and event handling policy
- `data`: Input interpretation (price field, returns mode, minimum bars) - `mean_estimator`: How the mean is computed (pluggable via `type`)
- `volatility_estimator`: How volatility is computed/normalized (pluggable via `type`)
- `deviation_detector`: How deviation events are triggered (pluggable via `type`)
- `reversion_criteria`: What qualifies as a successful reversion (pluggable via `type`)
- `failure_criteria`: What qualifies as event failure (pluggable via `type`) - `scoring`: Aggregation rules for scoring completed events
- `diagnostics`: Optional diagnostics capture

### Canonical Example

```yaml
config_version: 1
engine:
    allow_overlapping_events: false
    freeze_mean_on_event: true
    freeze_volatility_on_event: true
    max_active_events: 1
    data:
        price_field: close
        returns_mode: log
        min_bars_required: 100
    mean_estimator:
        type: rolling_sma
        params:
            window: 50
    volatility_estimator:
        type: ewma
        params:
            window: 30
            min_volatility: 0.0005
            volatility_unit: returns
    deviation_detector:
        type: zscore
        params:
            threshold: 1.75
            min_absolute_move: 0.002
    reversion_criteria:
        type: soft_band
        params:
            z_tolerance: 0.4
    failure_criteria:
        type: composite
        params:
            max_duration: 40
            max_zscore: 3.5
    scoring:
        by_direction: true
        by_volatility_bucket: true
        volatility_buckets: 5
        record_empty_scores: false
    diagnostics:
        enabled: true
        record_event_paths: true
        record_max_excursion: true
        record_time_to_resolution: true
```

### Versioning

- `config_version` is required.
- Only `1` is currently supported.
- Unsupported versions fail validation.

### `engine`
Controls global orchestration and event concurrency.

| Field | Type | Constraints | Meaning |
|---|---|---|---|
| `allow_overlapping_events` | bool | - | Allow multiple active events at the same time |
| `freeze_mean_on_event` | bool | - | Freeze mean at event start (recommended for interpretability) |
| `freeze_volatility_on_event` | bool | - | Freeze volatility at event start |
| `max_active_events` | int | `>= 1` | Upper bound on simultaneous active events |

Notes:
- The default mode is single-event (most robust and easiest to reason about).
- If `allow_overlapping_events` is `false`, `max_active_events` should remain `1`.

### `data`
Defines how inputs are interpreted.

| Field | Type | Constraints | Meaning |
|---|---|---|---|
| `price_field` | str | - | Field/column name used as the price series |
| `returns_mode` | enum | `log \| simple \| none` | How returns are computed/used (if needed by volatility estimation) |
| `min_bars_required` | int | `>= 1` | Minimum number of bars required to process a series |

### Pluggable Components: `type` + `params`
Each pluggable component uses the same shape:
```yaml
component_name:
  type: some_type
  params: ...
```

- `type` selects an implementation.
- `params` is validated according to the chosen `type`.
- Unknown `type` values or invalid `params` fail validation.

#### `mean_estimator`
Computes the reference mean. Common options:
- `rolling_sma`: Rolling simple moving average

Example:
```yaml
mean_estimator:
  type: rolling_sma
  params:
    window: 50
```

#### `volatility_estimator`
Computes volatility used for normalization (e.g., z-scores). Common options:
- `ewma`: Exponentially weighted moving volatility

Example:
```yaml
volatility_estimator:
  type: ewma
  params:
    window: 30
    min_volatility: 0.0005
    volatility_unit: returns
```

Parameter notes:
- `volatility_unit` must be `returns` or `price` and must match how deviation is normalized.
- `min_volatility` prevents division-by-zero and extreme sensitivity in low-vol regimes.

#### `deviation_detector`
Defines when a deviation event starts. Common options:
- `zscore`: Start an event when `|z| >= threshold`

Example:
```yaml
deviation_detector:
  type: zscore
  params:
    threshold: 1.75
    min_absolute_move: 0.002
```

Parameter notes:
- `threshold` must be positive.
- `min_absolute_move` is an optional guard to suppress tiny excursions.

#### `reversion_criteria`
Defines when an event is considered successfully reverted. Common options:
- `soft_band`: Reversion occurs when `|z| <= z_tolerance`

Example:
```yaml
reversion_criteria:
  type: soft_band
  params:
    z_tolerance: 0.4
```

Notes:
- Reversion is defined using a tolerance band; exact equality with the mean is not used.

#### `failure_criteria`
Defines when an event is considered failed. Common options:
- `composite`: A combination of timeouts and/or max excursion thresholds

Example:
```yaml
failure_criteria:
  type: composite
  params:
    max_duration: 40
    max_zscore: 3.5
```

Notes:
- At least one failure rule must be provided (e.g., `max_duration` and/or `max_zscore`).

### `scoring`
Defines how completed events are aggregated into scores.

| Field | Type | Constraints | Meaning |
|---|---|---|---|
| `by_direction` | bool | - | Report separate scores for upward vs downward deviations |
| `by_volatility_bucket` | bool | - | Stratify scores by volatility regime buckets |
| `volatility_buckets` | int \| null | `>= 1` when enabled | Number of buckets (quantiles) used for stratification |
| `record_empty_scores` | bool | - | Emit results even if no events were detected |

### `diagnostics`
Controls optional, non-intrusive diagnostics capture.

| Field | Type | Constraints | Meaning |
|---|---|---|---|
| `enabled` | bool | - | Enable diagnostics collection |
| `record_event_paths` | bool | - | Record per-event paths (may increase memory use) |
| `record_max_excursion` | bool | - | Record maximum adverse excursion per event |
| `record_time_to_resolution` | bool | - | Record event duration metrics |

### Validation Behavior
Configuration is validated before any data processing begins:
- Unknown keys cause failure.
- Invalid `type` selections cause failure.
- Invalid `params` for a given `type` cause failure.
- Invalid cross-field combinations (e.g., missing `volatility_buckets` when bucketing is enabled) cause failure.

This ensures runs are deterministic, reproducible, and auditable.
