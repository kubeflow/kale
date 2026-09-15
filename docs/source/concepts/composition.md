# Composing Multiple Notebooks

A single notebook is not always the right unit of work. Preprocessing that
several projects share, a training notebook someone else owns, an evaluation
step you want to keep separate: these are naturally different notebooks, and
copying cells between them is how they drift apart.

A `notebook:` cell lets one notebook reference another. The referenced notebook
is compiled into the same pipeline as a **nested sub-pipeline**, keeping each
of its cells visible as its own step in the KFP UI.

## A first composition

Take a notebook that prepares data and a notebook that trains on it. Neither
knows about the other; each is a normal Kale notebook that you can still run
and compile on its own.

`preprocessing.ipynb`:

```python
# tag: step:load
dataset = pd.read_csv("data.csv")
```

`training.ipynb`:

```python
# tag: step:train
model = RandomForestClassifier().fit(dataset, labels)
```

Now a third notebook composes them. It contains nothing but two reference
cells:

| cell tags | cell source | cell metadata |
| --- | --- | --- |
| `notebook:preprocessing` | *(empty)* | `notebook_path: ./preprocessing.ipynb` |
| `notebook:training` | *(empty)* | `notebook_path: ./training.ipynb` |

Compiling that notebook produces one pipeline containing both:

```
  root pipeline
  ├── preprocessing   (sub-DAG)
  │     └── load-step
  └── training        (sub-DAG)
        └── train-step
```

We call the notebook holding the references the **root notebook**.

## Where the path lives

The tag names the reference; it does not contain the path. The path lives in
the cell's metadata, under `notebook_path`, and is resolved relative to the
notebook that contains the cell.

```json
{
  "metadata": {
    "tags": ["notebook:preprocessing"],
    "notebook_path": "./preprocessing.ipynb"
  }
}
```

The Kale panel writes both for you: choose the **Notebook** cell type and enter
a path. A reference cell holds no code of its own, so Kale places a comment in
it explaining that.

```{note}
The `Notebook` cell type is hidden by default in the JupyterLab panel. See
[Enabling the cell type](#enabling-the-cell-type) below, which also explains
what that setting does and does not control.
```

## How data crosses a notebook boundary

It crosses the same way it crosses a cell boundary: Kale finds the variables
one unit produces and another consumes, and marshals them between the two. See
[Data Passing & Marshalling](data-passing.md) for the mechanism.

The difference is only the level. Inside a notebook, Kale matches variables
between cells. In a composition, it matches them between whole notebooks, and
then hands each variable to the specific step inside the referenced notebook
that actually produces or consumes it.

So in the example above, `training` reads `dataset` and never defines it, while
`preprocessing` defines it. Kale therefore:

- orders `preprocessing` before `training`, with no `prev:` tag needed
- marshals `dataset` out of `load-step` and into `train-step` as a KFP artifact

Two referenced notebooks that share no variables get no edge between them, so
unrelated work still runs in parallel.

## Mixing steps and references

A root notebook can also carry its own `step:` cells alongside its references.
Its own steps become top-level components in the pipeline, next to the sub-DAGs.

| cell tags | source |
| --- | --- |
| `notebook:preprocessing` | *(empty)* |
| `notebook:training` | *(empty)* |
| `step:report` | `print(f"accuracy: {accuracy}")` |

A root step runs after everything above it in the notebook and before
everything below it, so a composition runs the way it reads. Variables cross
in both directions: a root step can feed a referenced notebook, and a
referenced notebook can feed a root step.

## What you get out

Each referenced notebook is compiled into its own importable module, written
next to the root notebook's generated DSL in `.kale/`. The root notebook's DSL
imports those modules and wires everything together.

Each module is a complete pipeline of its own, so you can read it, and run it
standalone, independently of the composition that imports it.

## Enabling the cell type

The `Notebook` cell type is gated behind the **Enable composable notebooks**
setting in the Kale panel's settings (JupyterLab **Settings → Settings Editor →
Kale**). It is off by default while the feature settles.

```{important}
The setting controls **only whether the cell type is offered in the
cell-metadata editor**. It does not gate compilation.

A notebook that already contains a `notebook:` cell compiles as a composition
whether or not the setting is on, and `kale --nb` never sees the setting at
all. "Off by default" means the cell type is hidden, not that composition is
inert.
```

## Current limitations

Each of these is reported at compile time rather than at pipeline runtime.

**Nested references are not supported.** A referenced notebook cannot itself
reference a third notebook. Reference every notebook from the root notebook
instead.

**A reference cell holds no code.** Putting code in a `notebook:` cell raises,
rather than silently dropping it:

> `` `notebook:training` cell contains code. A cell that references a notebook
> holds no code of its own. Move the code to its own `step:` cell. ``

Comments are fine, which is why the panel can leave an explanatory one there.

**A notebook cannot reference itself,** directly or through another notebook.
Reference cycles raise.

**A reference needs a path.** A `notebook:` cell with no `notebook_path` in its
metadata raises, rather than compiling to nothing.

**Untagged code after a reference needs an owner.** A reference breaks the cell
merge chain, so an untagged cell after one attaches to the next `step:` cell.
If there is no following step, it raises rather than being dropped.

**Two references cannot share a name.** Reference names have to be unique
within a root notebook, since each names a node in the same pipeline.

## Dive deeper

- [Cell Types & Annotations](cell-types.md), the full tag vocabulary
- [Data Passing & Marshalling](data-passing.md), how variables move between steps
- [Pipeline Compilation](compilation.md), how a notebook becomes KFP DSL
- `examples/composition/`, five runnable notebooks demonstrating both shapes
