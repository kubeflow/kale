# Contributing

This page is the shorter, docs-site-friendly version of
[CONTRIBUTING.md](https://github.com/kubeflow/kale/blob/main/CONTRIBUTING.md)
in the repository. If you're about to open a PR, start here and then read
the full document for release-engineering details.

## Before you start

If you haven't already, skim [Architecture](architecture/index.md) — it's a quick tour
of the codebase and saves a lot of time when you need to find the right
file to change.

## Prerequisites

- **Python 3.11+** (3.12 is recommended).
- **uv** — installed automatically by `make dev`, or manually:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Node.js 22+** and `jlpm` — only required if you're touching the
  labextension. `jlpm` ships with JupyterLab.
- **A Kubernetes cluster** (optional) — only needed when testing
  generated pipelines end-to-end.

## Set up your environment

```bash
git clone https://github.com/kubeflow/kale.git
cd kale

make dev          # one-time setup
make test         # run backend + labextension tests
make jupyter      # open JupyterLab with the extension loaded
```

You only need to re-run `make dev` after pulling changes that touch
`pyproject.toml` / `package.json`, or after `make clean`.

## Make targets you'll use

| Target                 | Description                                      |
| ---------------------- | ------------------------------------------------ |
| `make dev`             | One-time environment setup.                      |
| `make test`            | Run all tests (backend + labextension).          |
| `make test-backend`    | Backend tests only.                              |
| `make test-backend-unit` | Fast unit tests only.                          |
| `make test-labextension` | Labextension tests only.                       |
| `make lint`            | Run all linters.                                 |
| `make lint-backend`    | Ruff check on the Python package.                |
| `make lint-labextension` | ESLint + Prettier on the TypeScript source.    |
| `make format-backend`  | Auto-fix Ruff findings.                          |
| `make build`           | Build a wheel.                                   |
| `make docs`            | Build the docs site (this website).              |
| `make docs-serve`      | Build and serve docs locally on port 8000.       |

Run `make help` in the repository root for the full list.
## Local KFP development

To test a notebook against a local Kubeflow Pipelines (KFP) cluster, use:

```bash
make kfp-dev NB=examples/base/candies_sharing.ipynb
```

This target builds the local Kale wheel, ensures the KFP development environment is running, starts the wheel server, and submits the notebook to KFP. It stops the managed wheel server before rebuilding the wheel directory so an existing server cannot keep serving a deleted directory.

The default wheel-server port is `8765`; the KFP UI is forwarded to port `8080`. You can override these with `KFP_PORT` and `KFP_LOCAL_PORT`.

For manual control, use `make kfp-build`, `make kfp-serve`, `make kfp-compile NB=...`, and `make kfp-run NB=... KFP_HOST=...` separately. The local wheel index host can be configured with `KFP_HOST_ADDR`; its default is `host.k3d.internal` on Linux and `host.docker.internal` on other operating systems.


## Managing Python dependencies

Edit `pyproject.toml` under the right section:

- Runtime dependencies: `[project.dependencies]`
- JupyterLab runtime: `[project.optional-dependencies.jupyter]`
- Dev tools: `[project.optional-dependencies.dev]`
- Documentation: `[project.optional-dependencies.docs]`

Then update the lockfile with `make lock` and sync the environment with
`uv sync --all-extras`.

## Pre-commit hooks

Install pre-commit hooks with:

```bash
uv run pre-commit install
```

Installed hooks:

- `uv-lock` — ensure `uv.lock` is in sync.
- `trailing-whitespace`, `end-of-file-fixer` — standard hygiene.
- `ruff` — Python linting and formatting.

## Contributing to the docs

This docs site lives under `docs/source/` and is built with Sphinx + Furo
+ MyST Parser. To add or edit a page:

1. Drop a new `.md` or `.rst` file into the appropriate directory under
   `docs/source/`.
2. Reference it from the toctree in `docs/source/index.md` so it appears
   in the sidebar.
3. Run `make docs` to build the site locally.
4. Run `make docs-serve` to view it at <http://localhost:8000>.

API reference pages use Sphinx autodoc via `.. automodule::`. If you're
adding or modifying public Python API, make sure you use Google-style
docstrings (Napoleon is enabled) and add/update the corresponding page in
`docs/source/api/`.

## Development checklist

Before opening a pull request:

1. `make test` — all tests pass.
2. `make lint` — no linter findings.
3. If you changed the generated KFP DSL, update the golden fixtures under
   `kale/tests/assets/kfp_dsl/`.
4. If you changed public Python API, update the `docs/source/api/` pages.
5. If you added or changed a user-visible feature, update the relevant
   pages under `docs/source/user-guide/` or `docs/source/concepts/`.
6. Write a clear commit message describing the change and the motivation.

## Releasing

Release procedures are documented in
[RELEASE.md](https://github.com/kubeflow/kale/blob/main/RELEASE.md). If you
don't have publish rights, you don't need to worry about this file.

## Getting help

- **GitHub issues** — [github.com/kubeflow/kale/issues](https://github.com/kubeflow/kale/issues)
- **Slack** — `#kubeflow-ml-experience` on the Kubeflow Slack workspace
- **WG meetings** — ML Experience WG on the Kubeflow community calendar

Happy hacking!
