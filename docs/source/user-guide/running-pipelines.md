# Running Pipelines

Once your notebook is annotated, you can compile and run it three ways:

1. **CLI** — `kale --nb ...`, good for scripts and CI.
2. **JupyterLab extension** — interactive Compile and Run button.
3. **Compile-only** — inspect the generated KFP DSL before submitting.

All three call into the same underlying Python API, so the behavior is
identical.

## From the command line

The `kale` CLI is the fastest path to a running pipeline. The core
invocation is:

```bash
kale --nb path/to/notebook.ipynb
```

This compiles the notebook into `.kale/<pipeline_name>.kale.py` and exits.
To also submit the pipeline to a running KFP instance, add:

```bash
kale --nb path/to/notebook.ipynb \
     --kfp_host http://127.0.0.1:8080 \
     --run_pipeline
```

### Useful CLI flags

| Flag                   | Effect                                                         |
| ---------------------- | -------------------------------------------------------------- |
| `--nb`                 | Path to the notebook (required).                               |
| `--kfp_host`           | KFP API endpoint for upload and run.                           |
| `--upload_pipeline`    | Upload the pipeline without starting a run.                    |
| `--run_pipeline`       | Upload *and* create a run.                                     |
| `--pipeline_name`      | Override the pipeline name (default comes from notebook metadata). |
| `--experiment_name`    | Override the KFP experiment (default `Kale-Pipeline-Experiment`). |
| `--pipeline_description` | Set a pipeline description shown in the KFP UI.              |
| `--docker_image`       | Override the default base image for all steps.                 |
| `--debug`              | Keep intermediate files and print verbose logs.                |

See [CLI Reference](../api/cli.md) for the complete list.

## From the JupyterLab extension

Open your notebook in JupyterLab, click the Kale icon in the left sidebar,
and toggle the Kale panel on. At the bottom of the panel you'll see:

- **Pipeline Name** and **Experiment Name** — override notebook defaults.
- **Docker Image** — base image used for every step that doesn't declare
  its own via an `image:` tag.
- **Compile and Save** — generate the KFP DSL only.
- **Compile and Run** — generate, upload, and start a run.

The Deploy button streams progress through a notification area at the top
of the panel, and surfaces the KFP run URL when the run is created so you
can click straight through to the KFP UI.

## Compile-only mode

When you want to read or debug the generated code before sending it to KFP,
skip the `--run_pipeline` flag on the CLI (or use **Compile and Save** in
the extension). You'll end up with:

```
.kale/
├── my_notebook.kale.py
└── my_notebook.yaml       # KFP YAML IR (produced when running the DSL)
```

The `.kale.py` file is pure KFP v2 DSL. The `.yaml` file is the compiled
pipeline IR that can be manually uploaded to the KFP UI without using Kale's
"Compile and Run" button. You can:

- Read it line by line to verify that your step dependencies, inputs, and
  outputs look right.
- Run it directly (`python .kale/my_notebook.kale.py`) to reproduce KFP
  compilation errors locally.
- Edit it to experiment with changes before committing them to the
  notebook.

## Monitoring runs

Once a run is submitted, open the KFP UI and navigate to **Runs**. You can:

- Watch step status in real time.
- Click a step to see its logs, the generated component source, and
  artifact inputs/outputs.
- See pipeline parameters and pipeline metrics in the run summary.
- Compare two runs side by side from the Runs list.

Kale doesn't add any custom tracking on top of KFP — everything runs
through the standard KFP backend, so anything you can do with a hand-rolled
KFP pipeline, you can also do with a Kale-generated one.

## Environment variables

A few environment variables are useful when running Kale:

| Variable                 | Purpose                                                                                    |
| ------------------------ | ------------------------------------------------------------------------------------------ |
| `KF_PIPELINES_ENDPOINT`  | Default KFP API endpoint if `--kfp_host` is not set.                                       |
| `KF_PIPELINES_UI_ENDPOINT` | KFP UI URL used when Kale renders run links (standard KFP UI pattern).                   |
| `KALE_KFP_NAMESPACE`     | Default Kubernetes namespace for KFP API operations. Used when no namespace is set via an explicit argument or the saved config; falls back to `kubeflow` when unset. |
| `KALE_UPLOAD_LINK`       | Custom URL for pipeline upload links. Overrides the default KFP UI pattern.                |
| `KALE_RUN_LINK`          | Custom URL for pipeline run links. Overrides the default KFP UI pattern.                   |
| `KALE_PIP_INDEX_URLS`    | Comma-separated pip index URLs baked into the generated components (used for local dev).  |
| `KALE_PIP_TRUSTED_HOSTS` | Trusted hosts for HTTP pip index URLs.                                                     |
| `KALE_PYPI_PROD_URL`     | Production pip index URL baked into generated components. Defaults to `https://pypi.org/simple`. |

### Custom links

The `KALE_UPLOAD_LINK` and `KALE_RUN_LINK` variables allow you to customize the
URLs generated for viewing pipelines and runs. This is useful when using a
different UI than the standard Kubeflow Pipelines UI.

Values must start with `http://` or `https://`; if they don't, Kale will
log a warning and fall back to the default KFP UI links.

**Placeholders:**

- `KALE_UPLOAD_LINK`: `{pipeline_id}`, `{version_id}`, `{namespace}`
- `KALE_RUN_LINK`: `{run_id}`, `{namespace}`

The `KALE_PIP_*` variables are most useful when testing an unpublished version of Kale
against a local KFP cluster — see the "Testing with KFP Clusters" section
of [Contributing](../contributing.md).
