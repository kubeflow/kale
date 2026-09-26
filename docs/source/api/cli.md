# CLI Reference

Kale ships a single `kale` command-line entry point, declared as
`[project.scripts]` in `pyproject.toml`. It compiles (and optionally runs) a
notebook against Kubeflow Pipelines.

## `kale`

The primary CLI. Parses a notebook, builds the pipeline DAG, compiles it to
KFP v2 DSL, and optionally uploads and runs it.

```bash
kale --nb path/to/notebook.ipynb [options]
```

### General options

| Flag                  | Type   | Description                                                          |
| --------------------- | ------ | -------------------------------------------------------------------- |
| `--nb`                | str    | Path to the source notebook. **Required.**                           |
| `--upload_pipeline`   | flag   | Upload the compiled pipeline to KFP.                                 |
| `--run_pipeline`      | flag   | Upload and then create a KFP run.                                    |
| `--debug`             | flag   | Enable verbose logging.                                              |
| `--dev`               | flag   | Bake a local devpi index URL into generated components.              |
| `--pip-index-urls`    | str    | Comma-separated PEP 503 simple indexes baked into components.        |
| `--devpi-simple-url`  | str    | Devpi simple URL (used when `--dev` is set).                         |

### Notebook metadata overrides

All the flags in this group override the corresponding fields in the
notebook's Kale metadata. If both are set, the CLI value wins.

| Flag                      | Description                                                  |
| ------------------------- | ------------------------------------------------------------ |
| `--experiment_name`       | KFP experiment name. Default: `Kale-Pipeline-Experiment`.    |
| `--pipeline_name`         | Name of the deployed pipeline. Default: the notebook's `pipeline_name`, else its file name plus a hash of its path. |
| `--pipeline_description`  | Description shown in the KFP UI.                             |
| `--docker_image`          | Default base image for every step.                           |
| `--kfp_host`              | KFP API endpoint, as `<host>:<port>` or a full URL.          |
| `--storage-class-name`    | Storage class for pipeline-created volumes.                  |
| `--volume-access-mode`    | Access mode for pipeline-created volumes.                    |

### Examples

Compile only, leave the generated script in `.kale/`:

```bash
kale --nb examples/base/candies_sharing.ipynb
```

Compile, upload, and run on a local KFP port-forward:

```bash
kale --nb examples/base/candies_sharing.ipynb \
     --kfp_host http://127.0.0.1:8080 \
     --run_pipeline
```

Override pipeline naming:

```bash
kale --nb notebooks/my_pipeline.ipynb \
     --pipeline_name "weekly-churn" \
     --experiment_name "production" \
     --run_pipeline --kfp_host http://127.0.0.1:8080
```

## Environment variables

A few environment variables affect `kale`:

| Variable                  | Effect                                                                                 |
| ------------------------- | -------------------------------------------------------------------------------------- |
| `KF_PIPELINES_ENDPOINT`   | Default KFP API endpoint when `--kfp_host` is not provided.                            |
| `KF_PIPELINES_UI_ENDPOINT` | KFP UI URL used when rendering run links (standard KFP UI).                           |
| `KALE_UPLOAD_LINK`        | Custom URL for pipeline links (placeholders: `{pipeline_id}`, `{version_id}`, `{namespace}`). |
| `KALE_RUN_LINK`           | Custom URL for run links (placeholders: `{run_id}`, `{namespace}`).                    |
| `KALE_PIP_INDEX_URLS`     | Comma-separated list of pip indexes baked into generated components.                   |
| `KALE_PIP_TRUSTED_HOSTS`  | Trusted hosts for HTTP pip indexes (required when using HTTP URLs).                    |
| `KALE_DEV_MODE`           | Equivalent to passing `--dev`.                                                         |
| `KALE_DEVPI_SIMPLE_URL`   | Equivalent to `--devpi-simple-url` when `--dev` is set.                                |
| `KALE_PYPI_PROD_URL`      | Production pip index URL baked into generated components. Defaults to `https://pypi.org/simple`. |

See [Running Pipelines](../user-guide/running-pipelines.md) for concrete scenarios where
these are useful.
