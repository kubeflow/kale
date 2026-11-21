# KEP-0843: Mount PersistentVolumeClaims in Pipeline Steps

|                     |                                                    |
| ------------------- | -------------------------------------------------- |
| **Authors**         | [ada333](https://github.com/ada333)                |
| **Created**         | 2026-07-20                                         |
| **Status**          | Provisional                                        |
| **Relevant Issues** | https://github.com/kubeflow/kale/issues/843  https://github.com/kubeflow/kale/issues/856      |

## Table of Contents

- [Summary](#summary)
- [Motivation](#motivation)
  - [Goals](#goals)
  - [Non-Goals](#non-goals)
- [User Stories](#user-stories)
- [Background: How Kale Handles Data Today](#background-how-kale-handles-data-today)
- [Proposal](#proposal)
  - [Architecture](#architecture)
- [Design Details](#design-details)
  - [Frontend — Left Panel](#frontend--left-panel)
  - [Backend — Compiler](#backend--compiler)
  - [Backend — RPC](#backend--rpc)
  - [CLI](#cli)
  - [Notes/Constraints/Caveats](#notesconstraintscaveats)
  - [Risks and Mitigations](#risks-and-mitigations)
  - [Test Plan](#test-plan)
  - [Graduation Criteria](#graduation-criteria)
- [Implementation Plan](#implementation-plan)
- [Migration](#migration)
- [Implementation History](#implementation-history)
- [Drawbacks](#drawbacks)
- [Alternatives Considered](#alternatives-considered)
- [Consequences](#consequences)

---

## Summary

Add support for mounting Kubernetes PersistentVolumeClaims (PVCs) into Kale
pipeline step Pods via notebook metadata and the JupyterLab extension UI. Users
will be able to configure 0–N volumes per pipeline in the Left Panel sidebar.
The Kale compiler will add a `kfp.kubernetes.mount_pvc(...)` call for every
volume in notebook metadata on every pipeline step.

---

## Motivation

When running AI/ML workloads, large datasets and model artifacts are often
stored on high-performance storage exposed in Kubernetes as PVCs. Kale's
current KFP v2 code path (introduced in 2.x) does not support mounting PVCs
into pipeline step Pods. Users are forced to either:

1. Hand-edit the generated DSL to add `kubernetes.mount_pvc(...)` for every
   step after compilation, or
2. Route large data through Kale marshal + the KFP artifact store, which is
   inefficient for files that are already on a mounted filesystem.

Beyond inefficiency, pickle-based marshal has hard failure modes that a shared
PVC would avoid entirely:

- **Large datasets and models** — serializing and deserializing gigabyte-scale
  objects between steps is slow and often runs out of memory or artifact store
  quota.
- **Ephemeral shared state** — scratch space written by one step and consumed
  by the next (e.g. a temporary data store or checkpoint directory) has no
  natural representation as a KFP artifact.

Kale 1.x had a volumes feature using KFP v1 APIs (`VolumeOp`, `PipelineVolume`,
`add_pvolumes`). All of those APIs were removed in KFP v2. This KEP revives the
volumes feature using the current `kfp-kubernetes` extension library.

### Goals

1. Let users configure 0–N volumes (PVC name + mount path) per pipeline in the
   JupyterLab Left Panel sidebar.
2. Persist that configuration in notebook metadata.
3. Have the Kale compiler emit `kubernetes.mount_pvc(...)` for every step in
   the generated KFP v2 pipeline.
4. Optionally pre-fill volumes from the PVCs already mounted on the running
   notebook Pod ("use this notebook's volumes") via a checklist dialog with a
   "Select all" shortcut and per-volume checkboxes.
5. Show a combobox of available PVCs in the namespace (with suggestions from the
   cluster) alongside free-text input, always accessible regardless of API availability.
6. Optionally expose each volume's mount path as a Kale-managed environment
   variable (e.g. `KALE_VOLUME_MY_DATA`) so notebook code can reference paths
   symbolically instead of hardcoding strings.
7. Warn users when a configured PVC has `accessMode: ReadWriteOnce` (RWO) —
   in the UI if the access mode can be read from the cluster, and always at
   pipeline runtime via a logged warning at the start of each step.
8. Delete the deprecated `--storage-class-name` and `--volume-access-mode`
   CLI flags — they only apply to PVC creation which is out of scope, and
   leaving them in place causes confusion.

### Non-Goals

- Per-step volume selection — all steps receive the same set of volumes in v1.
- Automatically ordering parallel steps that share files on a PVC.
- Creating new PVCs from the Kale UI (`new_pvc`, `VolumeOp`) — mount existing
  PVCs only.
- Using PVCs as the Kale marshal transport — marshal continues to use KFP
  artifacts.
- Making PVC existence a hard compiler requirement — offline/CI compile must
  still work.
- Native K8s volume snapshots — letting users mount a PVC
  from a snapshot of their local volumes (or any other PVC), so each pipeline
  run operates on an isolated, point-in-time copy.
- Node affinity pinning for RWO volumes — automatically constraining all steps
  to the node where an RWO PVC is already bound, to prevent parallel steps
  from hanging when scheduled on different nodes.
- Runtime pre-flight PVC check — a dedicated first step or init container that
  verifies all configured PVCs exist before compute steps run; useful but adds
  complexity and latency, and would need a UI toggle for opt-in behaviour.

---

## User Stories

### Story 1: Notebook volume available in pipeline

A user creates a notebook in Kubeflow and mounts a PVC named `my-data` at
`/data` via the Kubeflow UI. Code in the notebook reads from `/data` fine.
When they compile a Kale pipeline, the step Pods do not have `/data` mounted
and the pipeline fails.

With this feature, the user clicks "Use notebook volumes" in the Volumes panel.
Kale calls the existing `nb.list_notebook_volumes` RPC and opens a selection dialog
listing all PVCs currently mounted on the notebook Pod. The dialog provides a "Select all" shortcut alongside per-volume checkboxes,
so the user can include all or any subset of the available volumes. The
user checks `my-data` and confirms. Kale pre-populates a volume entry for
each selected PVC. All pipeline steps then get `my-data` mounted at `/data`.

### Story 2: Mount an arbitrary PVC

A user knows their training data lives on PVC `training-data`. Their notebook
does not have it mounted. They open the Volumes panel, click "Add Volume",
select `training-data` from the PVC dropdown (or type it manually), set mount
path `/data`, and compile. All pipeline steps get `training-data` mounted at
`/data`.

### Story 3: Portable notebook with env var mount paths

A user maintains a notebook used both in a dev cluster (PVC `raw-data` mounted
at `/mnt/raw`) and a prod cluster (same PVC mounted at `/datasets`). They tick
"Expose as env var" on the `raw-data` volume entry. Kale shows the derived
name `KALE_VOLUME_RAW_DATA`. The user writes their notebook against that
variable:

```python
import os
RAW = os.environ["KALE_VOLUME_RAW_DATA"]
df  = pd.read_csv(f"{RAW}/train.csv")
```

In dev they compile with mount path `/mnt/raw`; in prod they change it to
`/datasets`. The notebook code is identical in both environments. Kale injects
the correct env var value into every step Pod at compile time.

### Story 4: Multiple volumes on all steps

A user needs datasets at `/data` (PVC `datasets`) and wants to write model
checkpoints to `/models` (PVC `model-store`). They add two volume entries. Both
PVCs are mounted at both paths on every step.

```python
# Inside a pipeline step — just normal file I/O, no Kale API needed
df = pd.read_csv("/data/train.csv")       # reads from datasets PVC
model.save("/models/checkpoint.pt")       # writes to model-store PVC
```

---

## Background: How Kale Handles Data Today

### Two data paths

Today Kale has one mechanism for moving data between pipeline steps. This KEP
introduces a second. They serve different purposes:

| Mechanism | For what | How data moves |
|-----------|----------|----------------|
| **Kale marshal + KFP artifacts** (existing) | Python variables between steps (`ins`/`outs`) | serialize → object store → deserialize |
| **PVC mounts (this KEP)** | Files on a shared filesystem (`/data/...`) | mounted volume; code uses paths directly |

These two paths are complementary, not competing. Once this KEP is implemented,
a step can simultaneously read `/data/train.csv` from a PVC and pass a
processed `DataFrame` to the next step via Kale's normal marshal mechanism.

### Why PVCs?

The KFP artifact store round-trip (serialize → upload → download → deserialize)
is negligible for small objects but expensive for large datasets, model
checkpoints, or files that are already on disk in the right format. A PVC mount
avoids that cost entirely: step B opens the same file step A wrote, with no
intermediate copy.

### Kale 1.x volumes (historical reference)

Kale 1.x had a full volumes feature using KFP v1 APIs:
- `dsl.PipelineVolume(pvc=...)` — reference an existing PVC
- `dsl.VolumeOp(...)` — create a new PVC for the run
- `task.add_pvolumes({mount_path: volume})` — attach all volumes to every step

The same volumes dict was applied to all steps. Per-step selection was not
supported.

Additionally, Kale 1.x used a marshal PVC (mounted at `/marshal`) as the
transport for inter-step variable passing, and integrated with Arrikto Rok for
snapshotting notebook PVCs before cloning them into pipeline steps. Both the
KFP v1 volume APIs and Rok were removed during the KFP v2 migration.

The data model (`VolumeConfig`, `PipelineConfig.volumes`) still exists in the
codebase but is not wired into the active KFP v2 compiler.

### KFP v2 volume mounting

KFP v2 uses the `kfp-kubernetes` extension for Kubernetes-specific Pod
configuration. Mounting a PVC looks like:

```python
from kfp import kubernetes

task = my_step()
kubernetes.mount_pvc(task, pvc_name="my-data", mount_path="/data")
```

Under the hood, `mount_pvc` appends a `PvcMount` protobuf message to the
task's `PlatformSpec`. At runtime, the KFP backend driver reads that spec and
patches the about-to-launch Pod with the corresponding `Volume` and
`VolumeMount` before the step container starts.

---

## Proposal

### Architecture

1. The user configures volumes in the **Left Panel → Volumes section** of the
   Kale UI.
2. The UI writes those entries into **`notebook metadata.volumes[]`** (saved in
   the notebook's cell metadata).
3. At compile time, the Kale backend reads the metadata and populates
   **`PipelineConfig` / `VolumeConfig`** (`backend/kale/pipeline.py`).
4. The compiler passes the volume list to **`pipeline_template.jinja2`**,
   which renders a `kubernetes.mount_pvc(...)` call for every step task in the
   generated pipeline.

Volumes are **pipeline-level** configuration. The same set of mounts is applied
to every step — consistent with Kale 1.x behavior and the dominant use case
(shared datasets available to all steps).



---

## Design Details

### Frontend — Left Panel

A new **Volumes** section is added directly to the Left Panel, alongside
Pipeline Metadata.

```
Kale Deployment Panel
├── Pipeline Metadata  (experiment, name, description, docker image)
├── Volumes                                                          ← NEW
│   ├── [ + Add Volume ]
│   │   └── (inline add-form, opens on click)
│   │       ├── [ "Select from notebook" button ]
│   │       │   └── Checklist of PVCs mounted on the notebook Pod
│   │       │       ├── [ Select all ]
│   │       │       ├── ☑ my-data      /data
│   │       │       ├── ☐ model-store  /models
│   │       │       └── [ Cancel ]  [ Add selected ]
│   │       ├── [ PVC dropdown/input            ] [ mount path ]
│   │       ├── ☐ Expose as env var
│   │       └── [ Cancel ]  [ Add volume ]
│   ├── Volume 1: [ PVC dropdown/input ] [ /data   ] [×]
│   │             ☑ Expose as env var → KALE_VOLUME_MY_DATA  [copy]
│   └── Volume 2: [ PVC dropdown/input ] [ /models ] [×]
│                 ☐ Expose as env var
└── Deploy button / progress
```

**Interactions:**

| Action | Behaviour |
|--------|-----------|
| Add Volume | Appends a blank `{ name: '', mount_point: '' }` entry to `metadata.volumes` |
| Remove (×) | Drops that entry from the list |
| "+ Add Volume" | Opens the inline add-form; does not commit anything until "Add volume" is confirmed |
| "Select from notebook" | Calls `nb.list_notebook_volumes` RPC and shows a checklist of PVCs currently mounted on the notebook Pod with a "Select all" shortcut and per-volume checkboxes; confirming with "Add selected" bulk-adds one entry per checked volume, bypassing the single-volume form |
| PVC field | Combobox — free-text input with suggestions populated from `list_pvcs` RPC; suggestions are shown when available but typing a name manually always works |
| Mount path | Free-text; must be unique across entries |
| "Expose as env var" checkbox | When checked, Kale derives an env var name from the PVC name (`KALE_VOLUME_<SCREAMING_SNAKE_CASE>`, e.g. `raw-data` → `KALE_VOLUME_RAW_DATA`) and shows it read-only next to the checkbox with a copy button; the compiler injects this variable into every step Pod with the mount path as its value |
| "Add volume" | Commits the new entry to `metadata.volumes` |
| "Cancel" | Closes the form without adding anything |
| Remove (×) | Drops an existing volume entry from the list |

**Light UI validation (warn, never block compile):**
- Duplicate mount paths across entries
- PVC name not found in the combobox suggestions
- Empty PVC name or mount path when the other field is set
- PVC has `accessMode: ReadWriteOnce` — shown only when the access mode can
  be read from the cluster via `list_pvcs`; silently omitted otherwise

Volumes are stored in `metadata.volumes` and saved to notebook metadata on
every change, matching the pattern used by other pipeline metadata fields.

### Backend — Compiler

`pipeline_template.jinja2` is extended to emit `mount_pvc` calls when
`volumes` is non-empty. The `volumes` field already exists in
`VolumeConfig` / `IKaleNotebookMetadata`; for v1, only `name`,
`mount_point`, and `type: "pvc"` are required:

```json
{
  "kubeflow_notebook": {
    "pipeline_name": "my-pipeline",
    "volumes": [
      { "name": "my-data-pvc",   "mount_point": "/data",   "type": "pvc", "env_var": true },
      { "name": "my-models-pvc", "mount_point": "/models", "type": "pvc", "env_var": false }
    ]
  }
}
```

The template renders a `kubernetes.mount_pvc(...)` call for every step task,
and a `kubernetes.add_env_variable(...)` call for each volume that has
`env_var: true`. The env var name is derived at compile time by uppercasing the
PVC name and replacing non-alphanumeric characters with underscores, prefixed
with `KALE_VOLUME_`:

```python
from kfp import dsl, kubernetes

@dsl.pipeline(name="my-pipeline")
def auto_generated_pipeline():
    task1 = step_one_step(...)
    kubernetes.mount_pvc(task1, pvc_name="my-data-pvc",   mount_path="/data")
    kubernetes.mount_pvc(task1, pvc_name="my-models-pvc", mount_path="/models")
    kubernetes.add_env_variable(task1, name="KALE_VOLUME_MY_DATA_PVC", value="/data")

    task2 = step_two_step(...)
    kubernetes.mount_pvc(task2, pvc_name="my-data-pvc",   mount_path="/data")
    kubernetes.mount_pvc(task2, pvc_name="my-models-pvc", mount_path="/models")
    kubernetes.add_env_variable(task2, name="KALE_VOLUME_MY_DATA_PVC", value="/data")
```

For each configured volume, the compiled pipeline also includes a helper call
at the start of every step function. When the step pod actually runs, that
call queries the Kubernetes API for the PVC's access mode and logs a prominent
warning if it is `ReadWriteOnce`:

```
[KALE WARNING] PVC "my-data" has accessMode ReadWriteOnce.
If parallel steps are scheduled on different nodes, pods waiting
to attach this volume will hang. Consider using an RWX storage
class or ensure all steps run on the same node.
```

The check is best-effort — if the pod's service account lacks permission to
`get` the PVC, it is silently skipped and the step proceeds normally.

`PipelineConfig.volumes` is wired through `nbprocessor.py` into the compiler
path. Today this field is populated from notebook metadata but is never passed
to `pipeline_template.jinja2` — adding that wiring is part of this KEP.

`kfp-kubernetes` is already declared as a dependency
(`kfp[kubernetes]>=2.16.0`); no new package is needed.

### Backend — RPC

The Left Panel's PVC dropdown needs to show which PVCs exist in the cluster
namespace. Rather than calling the Kubernetes API directly from the frontend,
the UI calls a new backend RPC that wraps the API call and handles auth/errors
in one place — consistent with how other cluster resources (e.g.
`list_notebook_volumes`, `list_notebooks`) are already exposed.

`list_pvcs` is added to `backend/kale/rpc/nb.py`:

```python
def list_pvcs(request):
    """List all PVCs in the current namespace."""
```

Returning an empty list on failure means the combobox shows no suggestions,
but the user can still type a PVC name manually.

The existing `nb.list_notebook_volumes` RPC (which returns PVCs mounted on the notebook
Pod) is reused as-is for the "Use notebook volumes" button.

### CLI

No new flags are required for v1. Volumes come from notebook metadata written by
the UI:

```bash
kale --nb my_notebook.ipynb
```

The existing `--storage-class-name` and `--volume-access-mode` flags will be
deleted — they only apply to PVC creation, which is out of scope, and leaving
dead flags in place causes confusion.

### Notes/Constraints/Caveats

1. **All volumes on all steps.** Every configured volume is mounted on every
   step Pod, even if a step never opens a file at that path. Unused mounts add
   negligible overhead (no data is copied; the kernel simply registers the
   mount). Per-step selection is deferred to a future iteration.

2. **PVC access modes are set in Kubernetes, not by Kale.** Whether a PVC is
   `ReadWriteOnce`, `ReadWriteMany`, or `ReadOnlyMany` is determined when the
   PVC is created — via `kubectl`, the Kubeflow UI, or a storage provisioner.
   Kale only mounts existing PVCs; it cannot change or inspect their access
   mode. The user is responsible for choosing the right storage class when
   creating the PVC.

3. **No automatic step ordering for file-only dependencies.** KFP schedules
   steps in parallel whenever the DAG allows it. Shared PVC files are invisible
   to the scheduler. When two steps share data only via a volume (no Kale
   variable edge between them), the user must either introduce a variable
   dependency or manually add `.after()` in the generated DSL. This is an edge
   case — in tagged notebooks, most ordering is already implied by variable
   flow.

4. **RWO volumes and parallel steps.** A `ReadWriteOnce` (RWO) PVC can
   typically be mounted read-write by only one node at a time. If the scheduler
   places parallel steps on different nodes, the second Pod may fail to attach
   the volume. Users with large datasets should prefer `ReadWriteMany` (RWM)
   storage classes for shared pipeline data.

5. **PVC existence is not checked at compile time.** A missing or
   wrong-namespace PVC causes the step Pod to fail at runtime with a standard
   Kubernetes mount error surfaced in the KFP UI. This is intentional: offline
   and CI compile must work without cluster access. No runtime pre-check is
   performed today either — see Open Questions.

6. **Marshalling is unchanged.** Kale variable passing between steps (`ins`/`outs`)
   continues to use the marshal + KFP artifact store path. PVCs are not the
   marshal transport.

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| RWO volume blocks parallel step Pod scheduling | Document clearly; recommend RWM storage class for shared datasets (see Open Question 3) |
| Concurrent writers corrupt shared files | Document; rely on DAG ordering or user-added `.after()` in DSL |
| Missing PVC causes step Pod failure at runtime | Soft UI warning for unknown PVC names; standard Kubernetes error surfaced in KFP UI (see Open Question 2) |
| No K8s API access breaks PVC dropdown | Combobox shows no suggestions but free-text entry still works; empty `list_pvcs` return on any exception |
| RBAC prevents `list` PVCs in namespace | Same fallback; no hard dependency on listing |
| `kfp-kubernetes` import added unconditionally | Import only when `volumes` is non-empty in the template |

### Test Plan

- **Unit tests** (`test_rpc_nb.py`): `list_pvcs` returns the correct PVC names
  with a mocked Kubernetes client; returns an empty list on API error.
  `list_notebook_volumes` pre-fill populates entries matching the notebook Pod's mounts.
- **Unit tests**: `VolumeConfig` parsing (name, mount point, type); template
  rendering with 0, 1, and N volumes; duplicate mount path detection; empty
  volume list produces no `mount_pvc` calls.
- **UI tests** (Playwright, `kale-ui-components.spec.ts`): Volumes section
  renders in the Left Panel; Add/Remove volume rows; combobox accepts free-text
  input; "Use notebook volumes" button pre-fills entries.
- **Golden-file tests**: compiled pipeline YAML compared against expected output
  for a notebook with configured volumes.
- **E2E tests**: compile a notebook with one PVC configured; run on a Kubeflow
  cluster with the PVC present; verify the step Pod mounts the volume and code
  can read/write the expected path - could be addition to the already existing e2e test.

### Graduation Criteria

- Volumes panel functional in the Left Panel (add, remove, pre-fill).
- Compiled pipeline YAML contains `kubernetes.mount_pvc(...)` for every
  configured volume on every step.
- Works end-to-end on a Kubeflow cluster with a real PVC.
- Unit,UI and e2e tests passing in CI.
- RWO/RWM caveats and parallel-step guidance documented.

---

## Implementation Plan

| Phase | Area | Work |
|-------|------|------|
| 1 | Backend | Wire `PipelineConfig.volumes` through `nbprocessor.py` into the new compiler path |
| 1 | Backend | Extend `pipeline_template.jinja2` to emit `kubernetes.mount_pvc(...)` per step |
| 1 | Backend | Add `list_pvcs` RPC in `rpc/nb.py` using existing `k8sutils.get_v1_client()` |
| 2 | Frontend | Add Volumes section to Left Panel; add/remove rows; save to `metadata.volumes` |
| 2 | Frontend | PVC combobox with suggestions from `list_pvcs` RPC; free-text always available |
| 2 | Frontend | "Use notebook volumes" button wired to existing `nb.list_notebook_volumes` RPC |
| 2 | Frontend | Light validation (duplicate paths, empty fields, unknown PVC name) |
| 3 | Tests | Unit + UI + golden-file + E2E tests |
| 3 | Docs | Update README; note RWO/parallel caveats and `.after()` workaround |

---

## Migration

No migration needed. The `volumes` field already exists in `VolumeConfig` and
`IKaleNotebookMetadata` with a compatible shape from Kale 1.x. Notebooks
without a `volumes` key in metadata compile exactly as before (empty list, no
`mount_pvc` calls emitted).

---

## Implementation History

- 2026-07-20: Initial KEP creation

---

## Drawbacks

- All steps receive all configured mounts regardless of whether they use the
  files. This is consistent with Kale 1.x but may be surprising to users who
  expect isolation between steps.
- Adds `from kfp import kubernetes` to generated pipelines that use volumes,
  making those pipelines non-portable to non-Kubernetes backends (acceptable
  since Kale targets Kubeflow on Kubernetes).

---

## Alternatives Considered

### Alternative 1: Per-step volume selection

Allow users to tag individual steps (via cell metadata) with which PVC mounts
they should receive.

**Rejected because**: significantly more complex UI (per-cell volume editor) and
compiler (step-level mount logic) for a v1 feature. Pipeline-wide mounts cover
the dominant use case (shared datasets available to all steps). Per-step
selection can be added later as an opt-in refinement without breaking the
pipeline-wide default.

### Alternative 2: Auto-add `.after()` between all steps sharing a PVC

Automatically serialize all steps that mount the same PVC to eliminate file
races.

**Rejected because**: with pipeline-wide mounts, every step mounts every PVC.
Auto-`.after()` would force all steps into a single chain, eliminating real
parallelism (e.g., two independent steps that both read from `/data` but never
write). Ordering is the user's responsibility when they share files via a
volume without a Kale variable edge.

### Alternative 3: Marshal data over a PVC instead of the artifact store

Route Kale variable passing (`ins`/`outs`) through a shared marshal PVC rather
than the KFP artifact store, as Kale 1.x did.

**Rejected because**: KFP v2 artifact passing is the supported, portable,
cache-aware model. PVCs for marshal require cluster-specific storage
(particularly RWM), couple data passing to Kubernetes storage classes, and lose
caching and lineage tracking. PVCs for user data (this KEP) and artifacts for
Kale variables are complementary.

### Alternative 4: Rok clone / snapshot for notebook volumes

Snapshot the notebook Pod's PVCs and mount clones into pipeline steps (as Kale
1.x did with Arrikto Rok).

**Rejected because**: Rok was removed in #460 and is no longer a dependency.
For the "use this notebook's volumes" case, mounting the same existing PVC
directly is simpler and sufficient for RWM volumes. RWO contention with the
running notebook is a known limitation, documented in the caveats.

---

## Consequences

### Positive

- Users can read/write large datasets in pipeline steps without the
  serialize/deserialize overhead of the KFP artifact store.
- The "PVC works in my notebook but not my pipeline" problem (User Story 1) is
  addressed.
- Consistent with the KFP v2 / `kfp-kubernetes` recommended pattern for
  Kubernetes-specific Pod configuration.
- Reuses existing Kale data model (`VolumeConfig`) and Kubernetes client
  infrastructure (`k8sutils`, `podutils`).
- No new dependencies — `kfp-kubernetes` is already declared.

### Negative

- All steps get all mounts regardless of use — minor overhead; potential
  confusion if a user adds a sensitive PVC expecting only specific steps to
  see it.
- RWO volumes and parallel steps require user awareness of Kubernetes storage
  semantics.

### Neutral

- Kale marshal + artifact store path is unchanged. This KEP does not affect
  variable passing between steps.
- The generated pipeline YAML is Kubernetes-specific (uses `PlatformSpec`).
  This is already the case for other `kfp-kubernetes` features in Kale.

---

## Open Questions

None.
