---
hide-toc: true
---

# Kale

```{raw} html
<div class="kale-hero">
  <p class="tagline">From Jupyter Notebook to Kubeflow Pipeline — Zero Boilerplate</p>
</div>
```

**Kale** (Kubeflow Automated pipeLines Engine) turns annotated Jupyter notebooks
into production-ready [Kubeflow Pipelines](https://www.kubeflow.org/docs/components/pipelines/)
without requiring you to write a single line of KFP SDK code.

Tag cells in your notebook, let Kale figure out the data dependencies between
them, and compile the whole thing into a KFP v2 pipeline you can run on any
Kubeflow cluster.


## Why Kale?

::::{grid} 1 2 2 2
:gutter: 3

:::{grid-item-card} No SDK boilerplate
Annotate cells, compile, run. Kale generates the KFP v2 DSL for you — no need
to learn components, artifacts, or Python decorators.
:::

:::{grid-item-card} Automatic data passing
Variables flow between steps as if you were still in a single notebook. Kale's
type-aware marshalling handles numpy, pandas, scikit-learn, PyTorch, Keras,
TensorFlow, XGBoost and more.
:::

:::{grid-item-card} JupyterLab integration
Tag cells visually, define step dependencies, and submit pipelines from the
Kale side panel inside JupyterLab 4.
:::

:::{grid-item-card} KFP v2 native
Compiles to the modern KFP v2 pipeline DSL with full artifact support. Runs on
any compliant Kubeflow Pipelines backend.
:::
::::

## Get started

::::{grid} 1 2 2 2
:gutter: 3

:::{grid-item-card} {octicon}`rocket` Quickstart
:link: getting-started/quickstart
:link-type: doc

Compile and run your first notebook on Kubeflow Pipelines in a few minutes.
:::

:::{grid-item-card} {octicon}`book` Core Concepts
:link: concepts/index
:link-type: doc

Understand cell annotations, data marshalling, and how Kale compiles to KFP.
:::

:::{grid-item-card} {octicon}`tools` User Guide
:link: user-guide/annotating-notebooks
:link-type: doc

Practical walkthroughs for annotating, parameterizing, and running pipelines.
:::

:::{grid-item-card} {octicon}`code` API Reference
:link: api/pipeline
:link-type: doc

Python API for the Pipeline, Step, Compiler and marshalling modules.
:::
::::

## Kale in the Kubeflow ecosystem

Kale is part of the Kubeflow **ML Experience Working Group**, alongside the
[Kubeflow SDK](https://sdk.kubeflow.org/), [Kubeflow Pipelines](https://www.kubeflow.org/docs/components/pipelines/)
and [Kubeflow Notebooks](https://www.kubeflow.org/docs/components/notebooks/).
It lives at the notebook layer — where data scientists prototype — and bridges
the gap to the pipeline layer, where production workloads run.

If KFP is the "how" of running ML pipelines on Kubernetes, Kale is the "what
you meant": take the notebook you already have, and turn it into a pipeline
without rewriting anything.

## Community

- **GitHub**: [kubeflow/kale](https://github.com/kubeflow/kale)
- **Slack**: [#kubeflow-ml-experience](https://kubeflow.slack.com/) on the Kubeflow workspace
- **Working group**: ML Experience WG meetings — see the [Kubeflow community calendar](https://www.kubeflow.org/docs/about/community/)
- **Issues & feature requests**: [github.com/kubeflow/kale/issues](https://github.com/kubeflow/kale/issues)

```{toctree}
:hidden:
:caption: Getting Started

why-kale
getting-started/installation
getting-started/quickstart
```

```{toctree}
:hidden:
:caption: Core Concepts

concepts/index
concepts/cell-types
concepts/data-passing
concepts/compilation
```

```{toctree}
:hidden:
:caption: User Guide

user-guide/annotating-notebooks
user-guide/pipeline-parameters
user-guide/volumes
user-guide/running-pipelines
user-guide/troubleshooting
```

```{toctree}
:hidden:
:caption: Architecture

architecture/index
```

```{toctree}
:hidden:
:caption: API Reference

api/pipeline
api/step
api/compiler
api/marshal
api/cli
```

```{toctree}
:hidden:
:caption: Project

roadmap
contributing
```
