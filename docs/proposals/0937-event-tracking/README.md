# KEP-0937: Event Tracking Facade for Kale


|                     |                                                   |
| ------------------- | ------------------------------------------------- |
| **Authors**         | [adrielparedes](https://github.com/adrielparedes) |
| **Created**         | 2026-08-14                                        |
| **Updated**         | 2026-08-14                                        |
| **Status**          | Draft                                             |
| **Relevant Issues** | https://github.com/kubeflow/kale/issues/937       |


## Table of Contents

- [KEP-0937: Event Tracking Facade for Kale](#kep-0937-event-tracking-facade-for-kale)
  - [Table of Contents](#table-of-contents)
  - [Summary](#summary)
  - [Motivation](#motivation)
    - [Goals](#goals)
    - [Non-Goals](#non-goals)
  - [User Stories](#user-stories)
    - [Story 1: Product Manager Analyzing Feature Adoption](#story-1-product-manager-analyzing-feature-adoption)
    - [Story 2: Platform Team Deploying Kale Without Analytics](#story-2-platform-team-deploying-kale-without-analytics)
    - [Story 3: Downstream Distributor Adding a Custom Backend](#story-3-downstream-distributor-adding-a-custom-backend)
  - [Proposal](#proposal)
    - [Architecture](#architecture)
    - [Entry Point Discovery](#entry-point-discovery)
    - [JupyterLab UI Event Routing](#jupyterlab-ui-event-routing)
  - [Design Details](#design-details)
    - [EventTracker Protocol](#eventtracker-protocol)
    - [Noop Backend (Default)](#noop-backend-default)
    - [Configuration](#configuration)
    - [Anonymous Identity](#anonymous-identity)
    - [Event Schema](#event-schema)
    - [Proposed Events](#proposed-events)
      - [Reserved Properties](#reserved-properties)
    - [File Structure](#file-structure)
    - [Notes/Constraints/Caveats](#notesconstraintscaveats)
    - [Risks and Mitigations](#risks-and-mitigations)
    - [Test Plan](#test-plan)
  - [Implementation Plan](#implementation-plan)
  - [Migration](#migration)
  - [Implementation History](#implementation-history)
  - [Drawbacks](#drawbacks)
  - [Alternatives Considered](#alternatives-considered)
    - [1. Instrument with OpenTelemetry spans instead of custom events](#1-instrument-with-opentelemetry-spans-instead-of-custom-events)
    - [2. Let each entry point (CLI, extension) track independently](#2-let-each-entry-point-cli-extension-track-independently)
    - [3. Ship backends in-tree as optional extras](#3-ship-backends-in-tree-as-optional-extras)
    - [4. Ship all backends in core with no optional extras](#4-ship-all-backends-in-core-with-no-optional-extras)
  - [Consequences](#consequences)
    - [Positive](#positive)
    - [Negative](#negative)
    - [Neutral](#neutral)
  - [Open Questions](#open-questions)



## Summary

Add an event tracking subsystem to Kale that captures user actions (compile, run,
configure, etc.) and forwards them to a pluggable analytics backend. The system
uses a facade pattern with a **Noop** default tracker, so deployments that do not
want analytics pay zero cost and require zero configuration. Core Kale ships
**only** the `EventTracker` protocol and `NoopTracker` — all backend
implementations live in separate repositories, discovered at runtime via Python
entry points.

## Motivation

Today there is no visibility into how data scientists use Kale — which features
are adopted, where users drop off, or what configuration patterns are common.
This lack of data makes it impossible to prioritize feature work based on actual
usage or to detect friction points before users report them.

Event tracking closes that gap by sending structured events to a store that can
be queried from a UI like Amplitude, Segment, or a self-hosted solution.

### Goals

1. Provide a single `EventTracker` protocol that all Kale entry points
  (JupyterLab extension, CLI, core engine) emit events through.
2. Ship a **Noop** backend as the default so tracking is opt-in with zero
  runtime cost when disabled.
3. Define a structured event schema that carries action metadata without
  notebook content or personally identifiable information.
4. Support pluggable backends discovered at runtime via Python entry points
  (`importlib.metadata`). Backend packages are published independently
   (e.g., `pip install kale-tracking-amplitude`) — none ship in core.
5. Route all events — including JupyterLab UI events — through the Python
  backend to keep tracker logic in one place.



### Non-Goals

- This KEP does **not** propose a telemetry or metrics pipeline (no timeseries,
no Prometheus integration).
- This KEP does **not** define a cross-component event tracking standard for
other Kubeflow projects. The facade is scoped to Kale; other components may
adopt the pattern independently.
- This KEP does **not** cover dashboarding, alerting, or analytics UI — those
are concerns of the chosen backend.
- This KEP does **not** introduce user-identifiable tracking. Anonymous IDs are
the default; any richer identification is opt-in.

---



## User Stories



### Story 1: Product Manager Analyzing Feature Adoption

A product manager wants to know which Kale features are actually used and where
users drop off in the compile-and-run workflow. With an Amplitude backend
enabled, they can query event streams to see that 80% of users compile but only
40% submit a run, indicating friction in the run step.

### Story 2: Platform Team Deploying Kale Without Analytics

A platform team deploys Kale in an air-gapped environment. They do not configure
any tracking backend. The `NoopTracker` is active by default — no events leave
the system, no external network calls are attempted, and there is no
performance overhead.

### Story 3: Downstream Distributor Adding a Custom Backend

A downstream distributor (e.g., Red Hat) needs to send events to an internal
analytics service. They publish a separate package that implements the
`EventTracker` protocol, registers it as a `kale.tracking.backends` entry
point, and configures the backend name in the Kale config file — without
forking or patching core Kale.

---



## Proposal



### Architecture

Introduce a `kale/tracking/` subsystem that implements the facade pattern:

1. An `EventTracker` protocol defines the contract (`track`, `identify`,
  `flush`, `shutdown`).
2. A `TrackerFactory` reads configuration (file or environment variable) and
  returns the appropriate backend instance.
3. The `NoopTracker` is the default — every method is a no-op, guaranteeing no
  network calls, no buffering, and no memory allocation for events.
4. Instrumented code always calls `tracker.track()` unconditionally; the active
  backend decides whether to send or discard.

This design means no conditional checks are scattered through the codebase and
no code path changes based on whether tracking is active.

### Entry Point Discovery

Core Kale ships **only** the `EventTracker` protocol and `NoopTracker`. All
backend implementations (Amplitude, Segment, custom HTTP, etc.) live in
**separate repositories** published as independent packages. The
`TrackerFactory` discovers installed backends at runtime via Python entry points
(`importlib.metadata.entry_points`), so anyone can implement and distribute a
backend without touching the Kale codebase.

```
# In kale-tracking-amplitude's pyproject.toml:
[project.entry-points."kale.tracking.backends"]
amplitude = "kale_tracking_amplitude:AmplitudeTracker"
```

The `TrackerFactory` uses `importlib.metadata.entry_points()` to discover all
installed backends by name. This means:

- Core Kale has **zero vendor dependencies** for tracking
- Backend authors own their release cadence and dependency surface
- Downstream distributors can ship private backends without forking Kale
- Entry point names must be unique across all installed packages. If multiple
packages register the same name, `importlib.metadata` returns all of them
and the resolved backend is undefined. The `TrackerFactory` will log a
warning and fall back to `NoopTracker` when a name resolves to more than
one entry point. Backend authors should choose a descriptive, unique name
(e.g., `amplitude`, `segment`, `mycompany_internal`)



### JupyterLab UI Event Routing

Events triggered by backend operations (compile, run) are tracked inline in
the server extension handlers that already exist — no new endpoints needed.
The frontend simply passes the `trigger` value as part of the existing RPC
payload.

Pure UI events (`extension_opened`, `extension_action`) have no corresponding
backend operation, so they require a dedicated lightweight endpoint on the
Kale server extension:

```
POST /kale/api/track
Content-Type: application/json

{
  "action": "extension_opened",
  "category": "UI",
  "properties": {
    "trigger": "sidebar"
  }
}
```

The handler is minimal — it constructs an `Event`, populates `context`
automatically, and forwards it to the active tracker:

```python
@app.route("/kale/api/track", methods=["POST"])
def handle_track():
    payload = request.json
    tracker.track(Event(
        action=payload["action"],
        category=payload.get("category", "UI"),
        properties=payload.get("properties", {}),
    ))
    return "", 204
```

This endpoint is intentionally thin:

- No authentication beyond what the Jupyter server already provides
- No response body — fire-and-forget from the frontend's perspective
- Validation is limited to required fields (`action`); unknown properties are
passed through
- No rate limiting — JupyterLab is a single-user application, so the only
client is the extension running in the same user's browser behind Jupyter's
existing authentication (XSRF tokens, session cookies). Abuse protection
at this layer would guard against a threat model where the attacker already
has kernel access and can execute arbitrary code.
- The `NoopTracker` makes this a no-op in deployments without tracking

The TypeScript extension calls this endpoint via the existing Jupyter
`ServerConnection` utilities, keeping the frontend free of any tracking
logic or configuration.

---



## Design Details



### EventTracker Protocol

```python
class EventTracker(Protocol):
    def track(self, event: Event) -> None: ...
    def identify(self, user_id: str, traits: dict | None = None) -> None: ...
    def flush(self) -> None: ...
    def shutdown(self, timeout: float = 3.0) -> None: ...
```

The `shutdown` method accepts a `timeout` parameter (in seconds) that defines
the maximum time the backend should block while flushing pending events. This
prevents hanging the process on exit when the network is slow or unavailable.

Backend implementations should inherit from `EventTracker` explicitly. Although
`Protocol` supports structural subtyping (duck typing), explicit inheritance
ensures type checkers catch signature mismatches at the class definition rather
than at distant call sites. External backends already depend on `kale` for the
`Event` model, so importing `EventTracker` adds no extra coupling. The backend
authoring guide will recommend this pattern.

That said, since `EventTracker` is a `Protocol`, backends that prefer not to
inherit can simply implement the same method signatures — Python's structural
subtyping will recognize them as compatible without an inheritance relationship.

### Noop Backend (Default)

The Noop tracker is the zero-cost default. It inherits from `EventTracker`
explicitly so that any signature mismatch is caught by type checkers at the
class definition:

```python
class NoopTracker(EventTracker):
    def track(self, event: Event) -> None:
        pass

    def identify(self, user_id: str, traits: dict | None = None) -> None:
        pass

    def flush(self) -> None:
        pass

    def shutdown(self, timeout: float = 3.0) -> None:
        pass
```

This guarantees:

- No network calls
- No buffering or memory allocation for events
- No configuration required
- No conditional checks scattered through the codebase — callers always call
`tracker.track()` regardless of whether tracking is active



### Configuration

Tracking is configured through the existing Kale config system:

```yaml
# ~/.config/kale/config.yaml
tracking:
  backend: "noop"            # "noop" or any installed entry point name
  batch_size: 50             # events per batch flush
  flush_interval_seconds: 30 # max seconds between flushes
  anonymous_id: true         # generate and persist a random UUID v4 to ~/.config/kale/anonymous_id
  backend_config: {}         # opaque dict passed to the backend's __init__
    # Each backend defines its own keys. Examples:
    #   api_key: "..."        (Amplitude)
    #   write_key: "..."      (Segment)
    #   endpoint: "https://..." (custom HTTP)
```

Environment variable override: `KALE_TRACKING_BACKEND=amplitude`

The `backend` value is resolved against the `kale.tracking.backends` entry
point group. If no matching entry point is found and the value is not `"noop"`,
the factory logs a warning and falls back to `NoopTracker`.

### Anonymous Identity

When `anonymous_id` is enabled in the configuration, Kale generates a random
UUID v4 and persists it to `~/.config/kale/anonymous_id`. This ID is:

- **Random** — never derived from usernames, hostnames, or any other PII
- **Stable across sessions** — the same ID is reused until the file is deleted
- **Stable across reinstalls** — the file lives in user config, not in the
package installation directory, so reinstalling or upgrading Kale preserves it
- **User-resettable** — deleting the file causes a new ID to be generated on
the next tracked event

The ID is included in every event as `anonymous_id` and enables funnel analysis
(e.g., "80% of users compile but only 40% submit a run") without identifying
individual users. If `anonymous_id` is set to `false`, the field is omitted
from events entirely.

### Event Schema

```json
{
  "schema_version": 1,
  "action": "compile_started",
  "category": "COMPILE",
  "timestamp": "2026-08-04T14:30:00Z",
  "anonymous_id": "550e8400-e29b-41d4-a716-446655440000",
  "properties": {
    "trigger": "sidebar",
    "notebook_cell_count": 12,
    "step_count": 4,
    "has_volumes": true
  },
  "context": {
    "library": "kale",
    "library_version": "0.8.0",
    "os": "linux",
    "python_version": "3.11.9",
    "entry_point": "jupyterlab"
  }
}
```

The `schema_version` field is an integer that identifies the event schema
version. It is set to `1` for the initial release and will be incremented
when breaking changes are made to the schema. Backend implementations should
use this field to handle schema evolution gracefully.

The `context` field carries runtime metadata about the environment where the
event was produced. It is populated automatically by the tracking subsystem —
instrumented code does not need to set it. This gives backend authors a
standardized envelope for filtering and segmentation without polluting
`properties` with infrastructure concerns.

Reserved context keys:


| Key               | Description                                            |
| ----------------- | ------------------------------------------------------ |
| `library`         | Always `"kale"`                                        |
| `library_version` | Kale package version                                   |
| `os`              | Operating system (`linux`, `darwin`, `win32`)          |
| `python_version`  | Python runtime version                                 |
| `entry_point`     | How the user invoked Kale (`jupyterlab`, `cli`, `sdk`) |


Backend implementations may use context for routing, enrichment, or filtering.
Additional keys may be added in future versions; backends should tolerate
unknown keys.

Events never include:

- Notebook source code or cell contents
- File paths beyond the working directory name
- User names, emails, or identifiable information (unless opted in)



### Proposed Events


| Event               | Category  | When                                                      |
| ------------------- | --------- | --------------------------------------------------------- |
| `compile_started`   | COMPILE   | User triggers compile                                     |
| `compile_completed` | COMPILE   | Compile finishes (includes step count, duration)          |
| `compile_failed`    | COMPILE   | Compile errors out (includes error category, not message) |
| `run_started`       | RUN       | Pipeline submitted to KFP                                 |
| `run_completed`     | RUN       | Pipeline run finishes (includes status)                   |
| `config_changed`    | CONFIGURE | User modifies pipeline config (includes which fields)     |
| `extension_opened`  | UI        | JupyterLab extension panel opened                         |
| `extension_action`  | UI        | Button click in the extension (includes action name)      |




#### Reserved Properties

Events carry action-specific data in `properties`. The following keys are
reserved with consistent semantics across all events that use them:


| Property         | Type         | Description                                                               |
| ---------------- | ------------ | ------------------------------------------------------------------------- |
| `trigger`        | string       | UI surface that initiated the action (`sidebar`, `toolbar`, `cli`, `api`) |
| `duration_ms`    | int          | Elapsed time for completed/failed operations                              |
| `step_count`     | int          | Number of pipeline steps involved                                         |
| `error_category` | string       | High-level error class (not the raw message)                              |
| `fields_changed` | list[string] | Config field names that were modified                                     |


The `trigger` property should be present on any event that can be initiated
from multiple UI surfaces, so analysts can compare adoption across entry points
without needing separate event names per surface.

### File Structure

```
kale/tracking/
    __init__.py          # Public API: get_tracker(), track()
    event.py             # Event and EventCategory models
    tracker.py           # EventTracker protocol/ABC
    config.py            # TrackingConfig (integrates with kale/config/)
    factory.py           # TrackerFactory — discovers backends via entry points
    noop.py              # NoopTracker (default, always available)
```



### Notes/Constraints/Caveats

1. **Community-first packaging.** Core Kale ships **only** the `EventTracker`
  protocol and `NoopTracker`. All backend implementations live in separate
   repositories. The `TrackerFactory` discovers installed backends at runtime
   via entry points, so anyone can implement and distribute a backend without
   touching the Kale codebase.
2. **JupyterLab event routing.** All events, including pure UI events
  (`extension_opened`, `extension_action`), route through the Python backend.
   Backend operations use existing RPC handlers; pure UI events use the
   dedicated `POST /kale/api/track` endpoint. This keeps configuration and
   tracker logic in one place and avoids duplicating infrastructure in
   TypeScript.
3. **Batching and shutdown.** Events are flushed on process exit using an
  `atexit` hook and `SIGTERM` handler. Short CLI runs produce only a few
   events, so the flush is cheap. A short timeout (2–3s) prevents blocking on
   slow networks.
4. **Backend** `track()` **should return promptly.** The `EventTracker` protocol
  does not prescribe whether `track()` is synchronous or asynchronous — that
   is an implementation detail. However, since callers invoke `track()` inline
   during compile and run operations, backend authors should ensure `track()`
   returns promptly (e.g., by buffering events in memory and flushing
   asynchronously). The backend authoring guide will include this as a
   documented recommendation.
5. **Error handling is a backend responsibility.** Backend implementations
  must catch all exceptions internally and never propagate them to callers.
   Tracking failures must be invisible to the user — a broken backend must
   not crash a compile or run operation. Backends should log errors using
   Python's standard `logging` module so failures are diagnosable without
   affecting the calling code.



### Risks and Mitigations


| Risk                                                                | Mitigation                                                                                                            |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **Privacy concern** — users worry about data collection             | Noop is the default; events never include notebook content or PII; anonymous IDs only                                 |
| **Performance overhead** when tracking is enabled                   | Batched async writes; configurable batch size and flush interval                                                      |
| **Vendor lock-in** to a specific analytics platform                 | Protocol-based design; backends are separate packages discovered via entry points — core has zero vendor dependencies |
| **Community resistance** to analytics in an open-source project     | Core ships only Noop; no vendor code in the repository at all                                                         |
| **Discoverability** — users don't know which backend packages exist | Document the entry point contract and maintain a list of known backends in the Kale docs (without owning them)        |




### Test Plan

- **Unit Tests**:
  - `NoopTracker` — verify all methods are callable and produce no side effects
  - `TrackerFactory` — verify entry point discovery loads a registered backend
  - `TrackerFactory` — verify fallback to `NoopTracker` on missing, invalid, or
  uninstalled backend name
  - `Event` model — verify serialization, required fields, category validation,
  and automatic context population
  - `TrackingConfig` — verify parsing from YAML and environment variable override
  - (Backend packages are responsible for their own unit tests)
- **Integration Tests**:
  - `TrackerFactory` integration with `KaleConfig` — verify the `tracking:`
  config section is correctly loaded from a real config file
  - Backend flush-on-shutdown — verify `atexit` hook fires and pending events
  are flushed within the timeout window
- **E2E Tests**:
  - Compile-and-run workflow with `NoopTracker` — verify no errors and no
  network calls (baseline regression test)
  - Compile-and-run workflow with a mock HTTP backend — verify events are
  received in the correct order with expected fields

Coverage targets:

- `kale/tracking/`: new package — target 90%+ coverage
- `kale/config/`: existing — no coverage regression expected

---



## Implementation Plan


| Phase | Description                                                                         |
| ----- | ----------------------------------------------------------------------------------- |
| 1     | `EventTracker` protocol, `NoopTracker`, `TrackerFactory` with entry point discovery |
| 2     | `Event` model, `TrackingConfig`, integration with Kale config system                |
| 3     | Instrument compile and run events in the core engine                                |
| 4     | `POST /kale/api/track` endpoint for pure UI events                                  |
| 5     | Instrument JupyterLab extension (pass `trigger`, call track endpoint)               |
| 6     | Entry point contract documentation and backend authoring guide                      |


---



## Migration

No migration needed. This is a purely additive feature:

- Existing Kale workflows are unaffected — compile and run behavior is unchanged
- The `tracking` config section is new — existing config files without it
default to `NoopTracker`
- No existing APIs are changed or deprecated

---



## Implementation History

- 2026-08-04: Initial proposal drafted

---



## Drawbacks

- **Maintenance burden.** The entry point contract becomes a public API surface
that must remain stable. Mitigated by keeping the `EventTracker` protocol
minimal and versioning it from the start. Backend maintenance is fully owned
by the backend authors, not the Kale team.
- **Perception risk.** Some open-source users are wary of any analytics
capability, even when opt-in. Mitigated by defaulting to Noop and being
transparent about what is and is not collected.
- **Event schema evolution.** Once downstream consumers depend on the event
schema, changing it requires coordination. Mitigated by versioning the schema
from the start and defining a compatibility policy at the stable graduation
milestone.

---



## Alternatives Considered



### 1. Instrument with OpenTelemetry spans instead of custom events

OpenTelemetry provides a mature, vendor-neutral telemetry framework. However, it
is designed primarily for distributed tracing and metrics, not for product
analytics events (feature adoption, user workflows). Mapping product events to
OTel spans creates an impedance mismatch — analytics backends expect event
semantics (action, category, properties), not trace semantics (spans, contexts,
baggage). A custom facade with a focused event model is a better fit.

### 2. Let each entry point (CLI, extension) track independently

This avoids a shared subsystem but duplicates tracker configuration, event
schema definitions, and backend integration in each entry point. It also makes
it impossible to correlate events across entry points in a single analytics
query. The facade pattern eliminates this duplication.

### 3. Ship backends in-tree as optional extras

Backends could live in the Kale repo as optional extras (`pip install kale[amplitude]`). Simpler to discover, but the Kale team inherits maintenance
for every vendor SDK, review burden for backends they don't use, and CI
complexity for optional dependency matrices. Entry point discovery pushes all of
that to backend authors while keeping the same install experience for users.

### 4. Ship all backends in core with no optional extras

Simplest packaging, but couples the community project to specific vendor SDKs
(Amplitude, Segment). Contributors who don't use these services still pay the
dependency cost. The entry point approach keeps the core dependency-free.

---



## Consequences



### Positive

- Zero-cost default — deployments without analytics pay nothing
- Complete decoupling from vendor SDKs in the core repository
- Any party can build and distribute a backend without Kale team involvement
- Structured events enable data-driven prioritization of feature work
- Single tracking path (Python backend) keeps configuration and logic in one place



### Negative

- The `EventTracker` protocol becomes a public API that must remain stable
- Backend discoverability relies on documentation rather than in-repo code
- Pure UI events require a new server extension endpoint (`POST /kale/api/track`)



### Neutral

- Backend authors are fully responsible for their own testing and releases
- Event schema is versioned from day one (`schema_version: 1`)

---



## Open Questions

1. **Consent UX**: Should Kale show a first-run prompt when a non-Noop backend
  is configured, or is the config file sufficient as explicit opt-in?
2. **Backend health checks**: Should the `TrackerFactory` verify that a backend
  can connect on startup, or silently degrade to Noop on failure?
3. **Rate limiting**: Should the core provide a rate limiter to protect backends
  from event storms (e.g., rapid compile retries), or leave that to backend
   authors?
