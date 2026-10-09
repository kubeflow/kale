# Cell Types & Annotations

Kale reads Jupyter cell **tags** — strings stored under `metadata.tags` in the
`.ipynb` — to decide what role each cell plays in the generated pipeline.
This page documents every tag Kale understands, with examples.

You can set these tags visually through the Kale JupyterLab side panel, or by
editing the notebook JSON directly.

## The full tag vocabulary

| Tag                         | Example                         | Effect                                                                 |
| --------------------------- | ------------------------------- | ---------------------------------------------------------------------- |
| `imports`                   | -                       | Cell is prepended to every pipeline step. **All `import` statements must live in an `imports` cell.** |
| `functions`                 | -                     | Cell is prepended to every step after `imports`. Put function and class definitions here. |
| `pipeline-parameters`       | -           | Variables defined here become KFP pipeline parameters.                 |
| `pipeline-metrics`          | -              | `print()` statements in the cell are converted to KFP pipeline metrics. |
| `step:<name>`               | `step:train_model`              | Declares (or appends to) a pipeline step named `<name>`.               |
| `prev:<step_name>`          | `prev:load_data`                | Adds a dependency from the current step to `<step_name>`.              |
| `notebook:<name>`           | `notebook:preprocessing`        | References another notebook, compiled into this pipeline as a nested sub-pipeline. The path lives in the cell's `notebook_path` metadata. |
| `skip`                      | -                          | Cell is excluded from the pipeline entirely.                           |
| `annotation:<key>:<value>`  | `annotation:team:ml`            | Adds a Kubernetes annotation to the step's pod.                        |
| `label:<key>:<value>`       | `label:env:prod`                | Adds a Kubernetes label to the step's pod.                             |
| `limit:<resource>:<value>`  | `limit:nvidia.com/gpu:1`        | Adds a Kubernetes resource limit to the step's pod.                    |
| `image:<image>`             | `image:pytorch/pytorch:2.0`     | Overrides the base image for this step only.                           |
| `cache:enabled` / `cache:disabled` | `cache:disabled`         | Opts the step into or out of KFP's built-in caching.                   |
| `report:enabled` / `report:disabled` | `report:disabled`      | Enables or disables HTML report generation for this step.              |


## Per-cell-type details

### `imports`

The `imports` cell is where **every module import in your notebook must
live**. Kale prepends this cell's source to every pipeline step's generated
component, so any step can assume those imports are available.

```python
# tag: imports
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
```

```{warning}
If you import a library in a `step` or `functions` cell, Kale will **not**
add it to the step's `packages_to_install` list, and the step will fail at
runtime with `ModuleNotFoundError` unless the base image happens to include
the package.
```

### `functions`

Put function and class definitions here. Like `imports`, this cell is
prepended to every step.

```python
# tag: functions
def clean(df: pd.DataFrame) -> pd.DataFrame:
    return df.dropna()

class FeaturePipeline:
    def __init__(self, model):
        self.model = model
```

Keep these definitions **pure**: no top-level executable statements, no
prints, no imports, no global state mutation.

### `pipeline-parameters`

Variables defined in a `pipeline-parameters` cell become top-level KFP
pipeline parameters. They become inputs to the `@kfp_dsl.pipeline` function
and can be overridden at submission time.

```python
# tag: pipeline-parameters
learning_rate = 0.01
batch_size = 128
num_epochs = 10
```

Supported parameter types are `int`, `float`, `str`, and `bool`. If you
declare the same parameter in multiple `pipeline-parameters` cells, the last
value wins.

### `pipeline-metrics`

Any `print(...)` statements in a `pipeline-metrics` cell are parsed out by
Kale's AST helper
({py:func}`kale.common.astutils.parse_metrics_print_statements`) and emitted
as KFP pipeline metrics, making them visible in the KFP UI's run metrics
tab.

```python
# tag: pipeline-metrics
print("accuracy:", accuracy)
print("f1:", f1_score)
```

### `step:<name>`

The workhorse tag. Any cell tagged `step:data_processing` contributes code
to a pipeline step named `data_processing`. Multiple cells can share the
same step name — they will be concatenated in notebook order.

```python
# tag: step:load_data
df = pd.read_csv("data.csv")
df = clean(df)
```

Dependencies are declared with `prev:`:

```python
# tags: step:train, prev:load_data
model = RandomForestClassifier()
model.fit(df.drop("y", axis=1), df["y"])
```

You can add as many `prev:` tags as you want — one per dependency.

### `notebook:<name>`

References another notebook. The referenced notebook is compiled into the same
pipeline as a nested sub-pipeline, with each of its own cells still visible as
a step.

Unlike every other tag, the value here does not carry the information Kale
needs: the tag names the reference, and the **path lives in the cell's
`notebook_path` metadata**, resolved relative to the notebook containing the
cell.

```json
{
  "metadata": {
    "tags": ["notebook:preprocessing"],
    "notebook_path": "./preprocessing.ipynb"
  }
}
```

The cell itself holds no code. Kale infers the ordering between referenced
notebooks from the variables they share, exactly as it does between cells, so
no `prev:` tag is involved.

The `Notebook` cell type is hidden in the JupyterLab panel unless the **Enable
composable notebooks** setting is on. That setting only controls the editor;
a notebook that already contains a `notebook:` cell compiles either way.

See [Composing Multiple Notebooks](composition.md) for the full picture,
including the current limitations.

### Per-step configuration

A step cell can carry additional tags to customize its pod spec:

```python
# tags: step:train_gpu, prev:prepare_data,
#       image:pytorch/pytorch:2.0-cuda12,
#       limit:nvidia.com/gpu:1,
#       annotation:team:ml,
#       label:env:prod,
#       cache:disabled,
#       report:disabled
```

- **`image:<image>`** — use a custom base image for just this step.
- **`limit:<resource>:<value>`** — request GPU, memory, or any other
  resource (e.g. `limit:memory:8Gi`).
- **`annotation:<k>:<v>`** / **`label:<k>:<v>`** — add Kubernetes metadata
  to the step's pod. Useful for cost allocation, scheduling hints, or
  integration with observability tooling.
- **`cache:disabled`** — opt the step out of KFP's caching. Use `cache:enabled`
  to force caching when it's been disabled globally.
- **`report:disabled`** — disable HTML report generation for this step. By
  default, each step produces an HTML artifact containing the rendered output
  of its notebook cells. Use this tag to skip report generation when you don't
  need it, reducing artifact storage overhead.

### `skip`

Cells tagged `skip` are dropped from the pipeline. Use them for exploratory
code or debugging that you want to keep in the notebook but not run on the
cluster.

```python
# tag: skip
df.describe()
df.plot.hist()
```

## Best practices

- **Keep `imports` at the top** of the notebook. Don't spread imports across
  cells — Kale won't pick them up.
- **Never mutate global state from inside a step**. If you need to configure
  a library (e.g. `warnings.simplefilter`), do it once in an `imports` or
  `functions` cell.
- **Use `pipeline-parameters` for values you want to tweak between runs**.
  Resist hard-coding hyperparameters inside step cells.
- **Use `skip` liberally** during development for cells that don't belong in
  the pipeline, like `df.head()` or plotting code.
- **Name your steps explicitly** — `step:load_data`, `step:train`,
  `step:evaluate` — rather than leaving them auto-named.

See [Troubleshooting](../user-guide/troubleshooting.md) for the common failure modes these
practices prevent.
