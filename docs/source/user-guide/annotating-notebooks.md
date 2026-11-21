# Annotating Notebooks

Kale turns cell tags into pipeline structure. You can set those tags two
ways:

1. **From the Kale JupyterLab extension** — point-and-click, recommended for
   interactive development.
2. **By editing notebook metadata directly** — useful for scripting, code
   review, and when you don't have JupyterLab running.

Both produce the same tags, so the resulting `.ipynb` looks identical either
way.

## Using the JupyterLab extension

After you run `make jupyter` (or start JupyterLab any other way with the
Kale extension installed), open a notebook and click the Kale icon in the
left sidebar. The Kale panel appears with a master toggle at the top.

When you enable Kale, two things happen:

1. Every notebook cell grows a Kale metadata row at the top showing its cell
   type (Imports, Functions, Step, ...), step name, and dependencies.
2. The side panel unlocks pipeline-level settings: pipeline name, experiment
   name, and description.

### Setting a cell's type

Click the cell type dropdown on the cell's Kale row. You'll see:

- **Imports** — tag the cell as `imports`.
- **Functions** — tag the cell as `functions`.
- **Pipeline Parameters** — tag the cell as `pipeline-parameters`.
- **Pipeline Metrics** — tag the cell as `pipeline-metrics`.
- **Step** — tag the cell as a pipeline step. When you pick this, you'll be
  prompted for the step name and given a dropdown of possible dependencies
  (other steps in the notebook).
- **Skip Cell** — tag the cell as `skip`.

### Setting step dependencies

For cells tagged as `Step`, the panel lets you pick zero or more previous
steps. Each choice becomes a `prev:<name>` tag. Kale validates the choices
so you can't create cycles.

### Pipeline-level settings

The side panel's pipeline settings form is mapped to fields on
{py:class}`kale.pipeline.PipelineConfig`. Changes are saved into the
notebook's top-level metadata under the `kubeflow_notebook` key, so they
travel with the notebook and show up on the next open.

### Submitting

The **Compile and Run** button invokes the Kale backend from the JupyterLab
extension, which compiles the pipeline with exactly the same code path as
`kale --nb ...` on the CLI, then uploads and runs it against the configured
KFP host.

## Editing metadata by hand

Each cell in a notebook is JSON. Kale tags live in `metadata.tags` as a list
of strings. A minimal step cell looks like this:

```json
{
  "cell_type": "code",
  "metadata": {
    "tags": ["step:load_data"]
  },
  "source": [
    "df = pd.read_csv('data.csv')\n"
  ]
}
```

A step with a dependency and a GPU request:

```json
{
  "cell_type": "code",
  "metadata": {
    "tags": [
      "step:train",
      "prev:load_data",
      "limit:nvidia.com/gpu:1",
      "image:pytorch/pytorch:2.0-cuda12"
    ]
  },
  "source": ["..."]
}
```

Pipeline-level Kale settings live on the notebook (not on a cell) under the
`metadata.kubeflow_notebook` key — these are the same fields the side panel
exposes.

### Runtime images

The `runtimeImages` setting maps display names to container image references
available in the **Base Image** selector when configuring a pipeline step. The
dictionary can be customized in **JupyterLab Settings → Kale → Runtime images**.
The default entries are:

```json
{
  "Python 3.12": "python:3.12",
  "PyTorch 2.0": "pytorch/pytorch:2.0",
  "TensorFlow latest": "tensorflow/tensorflow:latest"
}
```

Users can add, rename, or remove entries in JupyterLab settings. The selector
searches both names and image references. Custom references can also be entered
directly by typing the reference and pressing Enter. Kale stores the image
reference in the cell's `image:` tag, so the notebook and compiled pipeline do
not depend on the display name. The cell label shows the configured name and
image reference, shortening either when it is long. Hover over either to see
its full text. Existing settings containing an image list are
converted automatically; each reference initially serves as its own name until
renamed.

## Output artifacts

Kale passes a variable from one step to the next only when a later step
actually uses it. A variable that nothing downstream consumes is normally
dropped — including the "result" you leave on the last line of a cell, the
idiomatic Jupyter way of displaying a value.

Kale recognises that pattern: **if the last line of a step is a bare
variable name, the variable is automatically promoted to a KFP output
artifact**, even though no later step consumes it. You can then inspect and
download it from the run's step details in the KFP UI.

```python
model = train(dataset)
print(f"Training finished, accuracy={acc:.3f}")
model          # <- bare trailing variable: becomes a KFP output artifact
```

The artifact type is inferred from the variable name:

| Name contains        | KFP artifact type       |
| -------------------- | ----------------------- |
| `model`              | `Model`                 |
| `dataset` or `data`  | `Dataset`               |
| `metrics`            | `Metrics`               |
| `classification`     | `ClassificationMetrics` |
| anything else        | `Artifact`              |

Only a *bare name* on the last line triggers the promotion. These do
**not** create an artifact:

```python
print(model)   # a call, not a bare name
df.head()      # a method call
obj.attr       # an attribute access
b = a + 1      # an assignment
```

The variable must be defined in the step (or an ancestor), must not be a
pipeline parameter, and is not duplicated if the step already outputs it.
See the [RAG example notebook](https://github.com/kubeflow/kale/tree/main/examples/rag)
for this in action: its `create_vector_database` step ends with a bare
`chroma_db`, which shows up as a downloadable artifact in the KFP UI.

## Organising a notebook for Kale

A notebook that compiles well with Kale usually follows this order:

1. **One `imports` cell** at the top with every `import` statement.
2. **One or more `functions` cells** below with pure function and class
   definitions.
3. **One `pipeline-parameters` cell** declaring tunable inputs.
4. **A sequence of `step` cells**, each doing one logical thing, with
   `prev:` tags describing the DAG.
5. **Optional `pipeline-metrics` cells** at the end of training steps to
   surface accuracy / loss / etc. in the KFP UI.
6. **`skip` cells** wherever you want exploratory code to live without
   affecting the pipeline.

See the [examples](https://github.com/kubeflow/kale/tree/main/examples) gallery for notebooks that follow this pattern.
