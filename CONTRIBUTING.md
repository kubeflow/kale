# Contributing to Kale

This guide explains how to set up a development environment for Kale and contribute
to the project.

## Prerequisites

- **Python 3.12+**
- **uv** - Installed automatically by `make`, or manually: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Node.js 22+** and **jlpm** (for frontend development only - jlpm comes with JupyterLab)
- **Kubernetes cluster** (optional, for KFP testing only) - [minikube](https://minikube.sigs.k8s.io/) or [kind](https://kind.sigs.k8s.io/)

## Quick Start

```bash
make dev          # Run once to set up (installs Python + Node dependencies, builds extension)
make test         # Run tests
make jupyter      # Start JupyterLab
```

**Note:** You only need to run `make dev` once. After the initial setup, just use `make test`, `make jupyter`, etc. Run `make dev` again only if:
- You pulled changes that modified `pyproject.toml` or `package.json`
- You ran `make clean`
- Dependencies need to be reinstalled

Run `make help` to see all available commands.

## Available Commands

| Command | Description |
|---------|-------------|
| `make dev` | Set up development environment |
| `make test` | Run all tests |
| `make test-backend` | Run backend tests |
| `make test-backend-unit` | Run backend unit tests only |
| `make test-labextension` | Run labextension tests |
| `make test-e2e-install` | Install Playwright browsers (run once) |
| `make test-e2e` | Run Playwright e2e tests (experimental) |
| `make lint` | Run all linters |
| `make lint-backend` | Lint backend code (ruff) |
| `make lint-labextension` | Lint labextension code (eslint + prettier) |
| `make format-labextension` | Format labextension code |
| `make build` | Build wheel |
| `make kfp-build` | Build wheel for KFP cluster testing |
| `make kfp-serve` | Serve local wheel for KFP testing |
| `make kfp-compile NB=...` | Compile notebook with local wheel |
| `make kfp-run NB=... KFP_HOST=...` | Compile and run on KFP |
| `make jupyter` | Start JupyterLab |
| `make jupyter-kfp` | Start JupyterLab with KFP dev env vars |
| `make watch-labextension` | Watch labextension for changes |
| `make lock` | Update uv.lock |
| `make lock-upgrade` | Upgrade all dependencies |
| `make clean` | Clean all build artifacts |
| `make clean-venv` | Remove virtual environment only |

## Managing Dependencies

### Adding a Python Dependency

1. Edit `pyproject.toml`:
   - Backend dependencies: `[project.dependencies]`
   - Jupyter dependencies: `[project.optional-dependencies.jupyter]`
   - Dev dependencies: `[project.optional-dependencies.dev]`

2. Update the lockfile:
   ```bash
   make lock
   ```

3. Sync your environment:
   ```bash
   uv sync --all-extras
   ```

### Adding a JavaScript Dependency

```bash
cd labextension
uv run jlpm add <package-name>      # Production dependency
uv run jlpm add -D <package-name>   # Dev dependency
```

### Upgrading All Dependencies

```bash
make lock-upgrade
```

## Building Release Artifacts

Build the production wheel:

```bash
make build    # Creates: dist/kubeflow_kale-2.0.0a1-py3-none-any.whl
```

### Testing in a Fresh Environment

To test the wheel works correctly in isolation:

```bash
# Create a fresh virtual environment
mkdir /tmp/kale-test && cd /tmp/kale-test
uv venv && source .venv/bin/activate

# Install lean backend only
uv pip install /path/to/kale/dist/kubeflow_kale-2.0.0a1-py3-none-any.whl

# Or install with JupyterLab extension
uv pip install "jupyterlab>=4.0.0,<5" "/path/to/kale/dist/kubeflow_kale-2.0.0a1-py3-none-any.whl[jupyter]"

# Start JupyterLab
jupyter lab
```

## Testing with KFP Clusters

When testing compiled pipelines on a KFP cluster (e.g., Kind or Docker Desktop),
you need to serve your local wheel so the cluster can install it.

### Docker Host Configuration

For KFP pods to reach your local wheel server, they need to resolve `host.docker.internal`:

| Platform | Configuration |
|----------|---------------|
| **macOS (Docker)** | Works automatically |
| **Windows (Docker)** | Works automatically |
| **Linux (Docker)** | Add `--add-host=host.docker.internal:host-gateway` to `docker run` |
| **Kind on macOS/Windows** | Works automatically (uses Docker Desktop) |
| **Kind on Linux** | Configure Kind to use host network or extra port mappings |

**Linux Docker example:**
```bash
docker run --add-host=host.docker.internal:host-gateway ...
```

**Kind on Linux** - add to your Kind cluster config:
```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 8765
        hostPort: 8765
```

**Podman (experimental)** - `host.docker.internal` is not natively supported:
```bash
# Option 1: Add host manually
podman run --add-host=host.docker.internal:host-gateway ...

# Option 2: Use host network
podman run --network=host ...
```
### One-command KFP Development Workflow

For local development with a Kubeflow Pipelines (KFP) cluster, run:

```bash
make kfp-dev NB=examples/base/candies_sharing.ipynb
```

This target checks the wheel-server port, stops an existing managed wheel server before rebuilding the wheel directory, builds the local Kale wheel, ensures the KFP development environment is running, starts the wheel server, and submits the notebook to KFP.

The wheel server defaults to port `8765`, and the KFP UI defaults to port `8080`. Override these values with `KFP_PORT` and `KFP_LOCAL_PORT` when needed.

### Manual KFP Workflow

You can run the steps separately:

```bash
make kfp-build
make kfp-serve
make kfp-compile NB=examples/base/candies_sharing.ipynb
make kfp-run NB=examples/base/candies_sharing.ipynb KFP_HOST=http://localhost:8080
```

`make kfp-serve` builds the wheel, copies it to `.kfp-wheels/`, and starts an HTTP server. When configured, Kale's compiler includes the local package index in the generated pipeline so pipeline components can install the local wheel instead of PyPI.

### Wheel Server Host Address

`KFP_HOST_ADDR` configures the address KFP pods use to reach the local wheel server. The Makefile defaults to `host.k3d.internal` on Linux and `host.docker.internal` on other operating systems. Override `KFP_HOST_ADDR` if your cluster networking requires a different address.
### Extension Workflow (JupyterLab UI)

To use the Kale extension with your local wheel:

```bash
# Terminal 1: Serve the wheel
make kfp-serve

# Terminal 2: Start JupyterLab with KFP env vars
make jupyter-kfp
```

The `jupyter-kfp` target sets the required environment variables automatically.
When you click "Compile and Run" in the Kale panel, the generated pipeline
will include your local wheel URL and trusted host configuration.

> NOTE:
>
> If you are not using `kind` or on Linux you must set `KFP_HOST_ADDR` before running `make jupyter-kfp`.
>
> For example, `minikube` users should use `KFP_HOST_ADDR=host.minikube.internal`
>
> To let KFP access localhost you may also need to disable the firewall:
> `sudo systemctl stop firewalld`

### With KFP Host (Direct Submission)

If you have a KFP instance running and want to submit directly:

```bash
# Terminal 1: Serve the wheel
make kfp-serve

# Terminal 2: Compile and submit (env vars are set automatically)
make kfp-run NB=examples/base/candies_sharing.ipynb KFP_HOST=http://localhost:8080
```

## Versioning

- **Backend**: Version set in `kale/__init__.py` (`__version__`)
- **Labextension**: Version set in `labextension/package.json`

Both versions should match (PEP 440 for Python, semver for npm). Use `make check-versions` to verify.

## Live Reload

| Component | Live Reload? | Method |
|-----------|--------------|--------|
| Labextension | Yes | `make watch-labextension` + browser refresh (F5) |
| Backend | No | Restart Jupyter kernel (`0 0` in command mode) |

**Browser refresh vs Kernel restart:**
- **Browser refresh (F5)**: Reloads JupyterLab UI to pick up labextension (TypeScript/JS) changes
- **Kernel restart (`0 0`)**: Restarts the Python process to pick up backend (Python) changes. Press `0` twice in command mode, or use Kernel menu → "Restart Kernel"

Note: Python's import caching (`sys.modules`) means backend changes require a
kernel restart. However, `make test-backend` always runs with fresh imports.

## Testing

Backend tests compare generated DSL against golden files in `kale/tests/assets/kfp_dsl/`.
When modifying template output, update these fixtures.

```bash
make test-backend-unit   # Quick unit tests
make test-backend        # All backend tests
make test-labextension   # Labextension tests
make test                # Everything
```

## Pre-commit Hooks

Install pre-commit hooks to ensure code quality:

```bash
pip install pre-commit
pre-commit install
```

Hooks include:
- `uv-lock`: Ensures `uv.lock` is up to date
- `trailing-whitespace`: Removes trailing whitespace
- `end-of-file-fixer`: Ensures files end with newline
- `ruff`: Python linting and formatting

## Debugging

### VS Code

Open the project in VS Code - debug configurations are provided in `.vscode/launch.json`:
- Debug Current Test File
- Debug All Unit Tests
- Debug Kale CLI
- Debug JupyterLab


## Development Checklist

1. Set up your environment: `make dev`
2. Make your changes
3. Run tests: `make test`
4. Run linting: `make lint`
5. Update fixtures if template output changed
6. Commit your changes

## Releasing

See [RELEASE.md](RELEASE.md) for instructions on publishing to TestPyPI and PyPI.

Happy hacking! If anything in this guide is unclear, open an issue or PR with improvements.
