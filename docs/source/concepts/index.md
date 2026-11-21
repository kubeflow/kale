# How Kale Works

Kale turns an annotated Jupyter notebook into a Kubeflow Pipelines v2 pipeline
through a small, deterministic compilation pipeline. This page gives you a
mental model for each stage; the rest of the concepts section drills into
details.

## The big picture

```
  .ipynb notebook
       │
       ▼
┌─────────────────────┐
│ NotebookProcessor   │  parses cell tags, builds a DAG of Steps
└─────────────────────┘
       │
       ▼
┌─────────────────────┐
│ Dependency analysis │  static AST analysis finds shared variables
└─────────────────────┘
       │
       ▼
┌─────────────────────┐
│ Compiler            │  renders Jinja2 templates → KFP v2 DSL
└─────────────────────┘
       │
       ▼
  .kale/<name>.kale.py
       │
       ▼
┌─────────────────────┐
│ KFP SDK             │  compiles DSL → YAML IR → uploads to KFP
└─────────────────────┘
       │
       ▼
  Running pipeline on Kubeflow
```

## Stage 1 — Parsing the notebook

When you run `kale --nb <notebook>`, a
{py:class}`kale.processors.NotebookProcessor` reads the `.ipynb` file with
`nbformat` and walks every cell. Cell tags (stored in notebook metadata under
`tags`) tell Kale what to do with the cell:

- Cells tagged `imports` or `functions` are collected and will be **prepended
  to every pipeline step**, so every step has access to the same set of
  modules and helpers.
- Cells tagged `pipeline-parameters` define the KFP parameters of the
  generated pipeline.
- Cells tagged `step:<name>` become pipeline steps. Multiple cells can share
  the same step name and will be concatenated in notebook order.
- `prev:<other_step>` tags add dependency edges between steps.
- `skip` cells are excluded entirely — useful for exploration code.

The result is a {py:class}`kale.pipeline.Pipeline` object, which is a
{py:class}`networkx.DiGraph` where nodes are {py:class}`kale.step.Step`
instances.

## Stage 2 — Finding data dependencies

Having a DAG of steps is not enough. Kale also needs to know **which variables
flow between steps** — if step `B` reads a `DataFrame` that step `A`
produced, Kale has to save it in `A` and load it back in `B`.

To figure this out, Kale uses
{py:func}`kale.common.astutils.get_marshal_candidates`, a static-analysis
helper that walks the cell's AST to find:

- Names that are assigned in one step and read in another.
- Names that escape function bodies via return or assignment.
- Names introduced by the shared `imports` / `functions` cells (which are
  **not** treated as data, because they are available everywhere).

The output is a set of "marshal candidates" per step, which Kale later turns
into save/load calls in the generated DSL.

## Stage 3 — Compiling to KFP v2

Once Kale has a DAG of steps, each annotated with its inputs and outputs, the
{py:class}`kale.compiler.Compiler` renders two Jinja2 templates:

1. `nb_function_template.jinja2` generates a `@kfp_dsl.component` function
   per step. Each component:
   - Starts with the shared imports and function definitions.
   - Loads inputs via Kale's marshalling dispatcher.
   - Executes the original cell source code (verbatim).
   - Saves any outputs that downstream steps will consume.

2. `pipeline_template.jinja2` wraps all components in a single
   `@kfp_dsl.pipeline` function that wires tasks together according to the
   dependency graph and plumbs pipeline parameters through.

The result is assembled, formatted with `autopep8`, and written to
`.kale/<pipeline_name>.kale.py`. You can read it — it's plain KFP v2 DSL —
and even hand-tweak it if you need to.

## Stage 4 — Submitting to KFP

When you pass `--run_pipeline`, Kale hands the generated script to
{py:mod}`kale.common.kfputils`, which invokes the KFP SDK compiler to turn
the DSL into YAML IR, uploads it to KFP, and starts a run via the KFP REST
API. The pipeline name, experiment name, and KFP host all come from your
notebook's Kale metadata or from command line overrides.

## Why it's built this way

Kale's compilation pipeline is intentionally a **pure, deterministic
transformation**: notebook → DSL. That means:

- The output is just Python. No hidden runtime. You can inspect it, debug it,
  version-control it, and run it without Kale installed (once the pipeline is
  submitted, it's a KFP pipeline like any other).
- Cells run **as if they were in a single notebook** — the imports, functions
  and parameters are available everywhere, and data passing happens behind the
  scenes.
- Because the transformation is static, Kale can detect most common mistakes
  at compile time instead of failing at pipeline runtime.

## Dive deeper

- [Cell Types & Annotations](cell-types.md) — the full tag vocabulary
- [Data Passing & Marshalling](data-passing.md) — how marshalling works and which types are supported
- [Composing Multiple Notebooks](composition.md) — referencing one notebook from another
- [Pipeline Compilation](compilation.md) — the exact compilation pipeline, file by file
