# Multi-notebook composition

Five notebooks demonstrating how one notebook references another with a
`notebook:` cell, so several notebooks compile into a single Kubeflow pipeline.

See [Composing Multiple Notebooks](../../docs/source/concepts/composition.md)
for the concepts.

## The notebooks

There are two entry points and three notebooks they reference.

| Notebook | Role |
| --- | --- |
| `main.ipynb` | **Entry point.** References the three notebooks below and nothing else. |
| `main_mixed.ipynb` | **Entry point.** The same three references, plus a `step:` cell of its own. |
| `notebook_a.ipynb` | Produces `names`, `dataset` and `weights`. |
| `notebook_b.ipynb` | Consumes those, fits a `model` and a `weight_total`. |
| `notebook_c.ipynb` | Consumes the model, computes a `prediction`, reports a metric. |

`notebook_a`, `notebook_b` and `notebook_c` are ordinary Kale notebooks. None of
them mentions the others, and each can be compiled and run on its own. What
links them is that they share variable names, which is all Kale needs to order
them and pass data between them.

## The two shapes

**`main.ipynb`** holds only references. Every step in the pipeline comes from a
referenced notebook:

```
notebook-sequence
├── notebook-a   ── names-step, generate-step, assemble-step, weights-step
├── notebook-b   ── show-names-step, fit-step, package-step, aggregate-step
└── notebook-c   ── predict-step, report-step, combine-step, summary-step
```

**`main_mixed.ipynb`** is the same three references plus its own `step:final`
cell, which prints the `prediction` that `notebook_c` produced. Its own step
becomes a top-level component alongside the three sub-DAGs:

```
notebook-sequence-mixed
├── notebook-a   (sub-DAG)
├── notebook-b   (sub-DAG)
├── notebook-c   (sub-DAG)
└── final-step   (a step of the root notebook itself)
```

That difference is the point of shipping both: the first shows notebooks
composed end to end, the second shows a root notebook contributing work of its
own.

## What to look at

Nothing here declares an order. `notebook_b` uses `dataset`, which
`notebook_a` defines, so `notebook_a` runs first and `dataset` is marshalled
between them. Open `notebook_a.ipynb` and you will find no mention of
`notebook_b`, and no `prev:` tag anywhere across the three.

Note also that `weights` is produced by `notebook_a` and consumed by
`notebook_b`, while `names` is produced by `notebook_a` and consumed by both
`notebook_b` and `notebook_c`, so the dependency graph is not a straight line.

## Compiling

```console
$ cd examples/composition
$ kale --nb main.ipynb
```

That writes the generated DSL into `.kale/`: one module per referenced
notebook, plus the pipeline that imports them. Each module is a runnable
pipeline in its own right.

To compile and submit in one go:

```console
$ kale --nb main.ipynb --run_pipeline --kfp_host <your-kfp-endpoint>
```

In JupyterLab, open `main.ipynb`, enable Kale in the panel, and use **Compile
and Run**. The reference cells show as `notebook: <name>` chips.

> **Note**
> To author reference cells in the panel rather than just read them, turn on
> **Enable composable notebooks** in the Kale settings. Compiling these
> examples does not need it.
