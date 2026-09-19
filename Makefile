.PHONY: help dev install \
        test test-backend test-backend-unit test-labextension test-e2e test-e2e-install \
        lint lint-backend lint-labextension format-labextension format-backend \
        build \
        kfp-build kfp-serve kfp-compile kfp-run kfp-dev \
        kfp-dev-setup kfp-dev-start kfp-dev-stop kfp-dev-delete kfp-dev-status kfp-dev-upgrade \
        clean clean-venv lock lock-upgrade check-uv check-yarn-version \
        jupyter jupyter-kfp watch-labextension \
        docker-build docker-run \
        docs docs-serve docs-clean \
        release verify check-versions

UV := uv
# jlpm is a yarn wrapper provided by JupyterLab - use it for extension development
JLPM := $(UV) run jlpm

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

# Default target
.DEFAULT_GOAL := help

##@ General

help: ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\n$(BLUE)Kale Development Commands$(NC)\n\nUsage:\n  make $(GREEN)<target>$(NC)\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

check-uv: ## Verify uv is installed
	@command -v $(UV) >/dev/null 2>&1 || { \
		printf "$(YELLOW)uv not found. Installing...\n$(NC)"; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	}

check-yarn-version: ## Verify jlpm's Yarn matches the packageManager pin
	@pinned=$$(sed -n 's/.*"packageManager": *"yarn@\([^"]*\)".*/\1/p' labextension/package.json); \
	actual=$$($(JLPM) --version 2>/dev/null | tail -1); \
	if [ -z "$$pinned" ]; then \
		printf "$(YELLOW)No packageManager pin found in labextension/package.json.\n$(NC)"; \
		exit 1; \
	fi; \
	if [ "$$pinned" != "$$actual" ]; then \
		printf "$(YELLOW)Yarn mismatch: package.json pins yarn@$$pinned, jlpm provides $$actual.\n$(NC)"; \
		printf "$(YELLOW)Dependabot activates the pinned version via Corepack, so a mismatch makes its\n$(NC)"; \
		printf "$(YELLOW)yarn.lock updates fail 'jlpm install --immutable' in CI.\n$(NC)"; \
		printf "$(YELLOW)Fix: set packageManager to yarn@$$actual in labextension/package.json and\n$(NC)"; \
		printf "$(YELLOW)labextension/ui-tests/package.json, then regenerate both lockfiles with\n$(NC)"; \
		printf "$(YELLOW)'jlpm install --mode=update-lockfile'.\n$(NC)"; \
		exit 1; \
	fi; \
	printf "$(GREEN)Yarn $$actual (jlpm) matches the packageManager pin\n$(NC)"

##@ Installation

dev: check-uv ## Set up development environment
	@printf "$(BLUE)Setting up Kale development environment...\n$(NC)"
	@# Step 1: Install package to get jlpm available
	@# Skip the hatch jupyter-builder hook — we build the labextension explicitly below
	SKIP_JUPYTER_BUILDER=1 $(UV) sync --all-extras
	@# Step 2: Build labextension (requires jlpm from step 1)
	@# Guard first: a jlpm/packageManager mismatch silently breaks Dependabot's lockfile updates
	@$(MAKE) --no-print-directory check-yarn-version
	cd labextension && $(JLPM) install
	@# Clean tsbuildinfo cache before build (fixes incremental build issues after make clean)
	cd labextension && $(JLPM) clean:lib
	cd labextension && $(JLPM) build
	@# Step 3: Link extension for development
	$(UV) run jupyter labextension develop --overwrite .
	@# Step 4: Set up pre-commit hooks (Python + TypeScript/JavaScript linting)
	@$(UV) run pre-commit install 2>/dev/null || { \
		printf "$(YELLOW)Note: pre-commit hooks not installed (core.hooksPath is set globally).\n$(NC)"; \
		printf "$(YELLOW)To enable pre-commit hooks, run: git config --unset core.hooksPath\n$(NC)"; \
	}
	@printf "$(GREEN)Setup complete! Run 'make jupyter' to start JupyterLab\n$(NC)"

install: dev ## Alias for dev

##@ Testing

test: test-backend test-labextension ## Run all tests

test-backend: ## Run backend tests
	@printf "$(BLUE)Running backend tests...\n$(NC)"
	$(UV) run pytest kale/tests -vv

test-backend-unit: ## Run backend unit tests only
	@printf "$(BLUE)Running backend unit tests...\n$(NC)"
	$(UV) run pytest kale/tests/unit_tests -vv

test-labextension: ## Run labextension tests
	@printf "$(BLUE)Running labextension tests...\n$(NC)"
	cd labextension && $(JLPM) test

test-e2e-install: ## Install Playwright browsers (run once)
	@printf "$(BLUE)Installing Playwright dependencies...\n$(NC)"
	cd labextension/ui-tests && $(JLPM) install
	cd labextension/ui-tests && $(JLPM) playwright install
	@printf "$(GREEN)Playwright installed!\n$(NC)"

test-e2e: ## Run Playwright e2e tests (experimental)
	@printf "$(BLUE)Running Playwright e2e tests...\n$(NC)"
	@printf "$(YELLOW)Note: e2e tests may timeout due to extension kernel startup\n$(NC)"
	cd labextension/ui-tests && $(JLPM) playwright test

##@ Linting

lint: lint-backend lint-labextension ## Run all linters

lint-backend: ## Lint backend code (ruff)
	@printf "$(BLUE)Linting backend...\n$(NC)"
	$(UV) run ruff check kale
	$(UV) run ruff format --check kale

lint-labextension: ## Lint labextension code (eslint + prettier)
	@printf "$(BLUE)Linting labextension...\n$(NC)"
	cd labextension && $(JLPM) lint:check

format-labextension: ## Format labextension code
	cd labextension && $(JLPM) prettier && $(JLPM) eslint

format-backend: ## Format backend code (ruff)
	$(UV) run ruff check --fix kale
	$(UV) run ruff format kale

##@ Building

build: ## Build wheel
	@printf "$(BLUE)Building wheel...\n$(NC)"
	$(UV) build
	@printf "$(GREEN)Wheel built: dist/\n$(NC)"

##@ KFP Development (replaces devpi workflow)

KFP_WHEEL_DIR ?= $(CURDIR)/.kfp-wheels
KFP_PORT ?= 8765
# Host address for KFP to reach the wheel server (Linux users: override with your host IP)
KFP_HOST_ADDR ?= host.docker.internal

kfp-build: ## Build wheel for KFP cluster testing (fixed version for reproducibility)
	@printf "$(BLUE)Building wheel...\n$(NC)"
	rm -f dist/kubeflow_kale-*.whl
	$(UV) build
	@# Create PEP 503 compliant simple index structure
	rm -rf "$(KFP_WHEEL_DIR)"
	mkdir -p "$(KFP_WHEEL_DIR)/kubeflow-kale"
	cp dist/kubeflow_kale-*.whl "$(KFP_WHEEL_DIR)/kubeflow-kale/"
	@# Generate index files for pip simple API
	@echo '<!DOCTYPE html><html><body><a href="kubeflow-kale/">kubeflow-kale</a></body></html>' > "$(KFP_WHEEL_DIR)/index.html"
	@cd "$(KFP_WHEEL_DIR)/kubeflow-kale" && for f in *.whl; do echo "<a href=\"$$f\">$$f</a><br>"; done > index.html
	@printf "$(GREEN)Wheel ready at $(KFP_WHEEL_DIR)\n$(NC)"

kfp-serve: kfp-build ## Serve wheel via HTTP for Kind/Docker clusters
	@printf "$(BLUE)Starting wheel server on port $(KFP_PORT)...\n$(NC)"
	cd $(KFP_WHEEL_DIR) && python3 -m http.server $(KFP_PORT)

kfp-compile: ## Compile notebook with local wheel (usage: make kfp-compile NB=path/to/notebook.ipynb)
	@test -n "$(NB)" || { printf "$(YELLOW)Usage: make kfp-compile NB=path/to/notebook.ipynb\n$(NC)"; exit 1; }
	@printf "$(YELLOW)Make sure 'make kfp-serve' is running in another terminal\n$(NC)"
	KALE_PIP_INDEX_URLS="http://$(KFP_HOST_ADDR):$(KFP_PORT)" \
	KALE_PIP_TRUSTED_HOSTS="$(KFP_HOST_ADDR)" \
	$(UV) run kale --nb $(NB)

kfp-run: ## Compile and run on KFP with local wheel (usage: make kfp-run NB=... KFP_HOST=...)
	@test -n "$(NB)" || { printf "$(YELLOW)Usage: make kfp-run NB=path/to/notebook.ipynb KFP_HOST=http://localhost:8080\n$(NC)"; exit 1; }
	@test -n "$(KFP_HOST)" || { printf "$(YELLOW)Error: KFP_HOST not set\n$(NC)"; exit 1; }
	@printf "$(GREEN)Using KFP at $(KFP_HOST)\n$(NC)"
	KALE_PIP_INDEX_URLS="http://$(KFP_HOST_ADDR):$(KFP_PORT)" \
	KALE_PIP_TRUSTED_HOSTS="$(KFP_HOST_ADDR)" \
	$(UV) run kale --nb $(NB) --kfp_host $(KFP_HOST) --run_pipeline

kfp-dev: ## Start KFP, build wheel, start wheel server, and run a notebook
	@test -n "$(NB)" || { echo "Usage: make kfp-dev NB=path/to/notebook.ipynb"; exit 1; }

	@echo "Ensuring KFP development environment is running..."
	@$(MAKE) kfp-dev-setup \
		KFP_CLUSTER_NAME="$(KFP_CLUSTER_NAME)" \
		KFP_PIPELINE_VERSION="$(KFP_PIPELINE_VERSION)" \
		KFP_LOCAL_PORT="$(KFP_LOCAL_PORT)" \
		KFP_PID_FILE="$(KFP_PID_FILE)"

	@$(MAKE) kfp-build

	@echo "Checking wheel server on port $(KFP_PORT)..."
	@if ! curl -sf "http://localhost:$(KFP_PORT)/kubeflow-kale/" >/dev/null; then \
		echo "Starting wheel server on port $(KFP_PORT)..."; \
		(cd "$(KFP_WHEEL_DIR)" && nohup python3 -m http.server "$(KFP_PORT)" \
			>/tmp/kale-kfp-wheel-server.log 2>&1 & \
			echo $$! > /tmp/kale-kfp-wheel-server.pid); \
		sleep 2; \
	else \
		echo "Reusing existing wheel server on port $(KFP_PORT)"; \
	fi

	@$(MAKE) kfp-run \
		NB="$(NB)" \
		KFP_HOST="http://localhost:$(KFP_LOCAL_PORT)"

##@ KFP Local Cluster (k3d — lightweight alternative to minikube)

KFP_CLUSTER_NAME ?= kale-kfp
KFP_PIPELINE_VERSION ?= 2.16.0
KFP_LOCAL_PORT ?= 8080
KFP_PID_FILE := $(CURDIR)/.kfp-dev-pf.pid

kfp-dev-setup: ## Create k3d cluster + install KFP standalone (~5 min, first time only)
	@bash scripts/kfp-dev-setup.sh setup "$(KFP_CLUSTER_NAME)" "$(KFP_PIPELINE_VERSION)" "$(KFP_LOCAL_PORT)" "$(KFP_PID_FILE)"

kfp-dev-upgrade: ## Upgrade KFP on existing cluster (usage: make kfp-dev-upgrade KFP_PIPELINE_VERSION=2.17.0)
	@bash scripts/kfp-dev-setup.sh upgrade "$(KFP_CLUSTER_NAME)" "$(KFP_PIPELINE_VERSION)" "$(KFP_LOCAL_PORT)" "$(KFP_PID_FILE)"

kfp-dev-start: ## Start existing cluster and port-forward KFP UI to localhost:8080
	@printf "$(BLUE)Starting k3d cluster '$(KFP_CLUSTER_NAME)'...\n$(NC)"
	@k3d cluster start $(KFP_CLUSTER_NAME) 2>/dev/null || { \
		printf "$(YELLOW)Cluster '$(KFP_CLUSTER_NAME)' not found. Run 'make kfp-dev-setup' first.\n$(NC)"; exit 1; \
	}
	@printf "$(BLUE)Switching kubectl context to k3d-$(KFP_CLUSTER_NAME)...\n$(NC)"
	@kubectl config use-context k3d-$(KFP_CLUSTER_NAME)
	@if [ -f "$(KFP_PID_FILE)" ]; then \
		kill $$(cat "$(KFP_PID_FILE)") 2>/dev/null || true; \
		rm -f "$(KFP_PID_FILE)"; \
	fi
	@printf "$(BLUE)Waiting for KFP pods to be ready...\n$(NC)"
	@kubectl wait pods -l "application-crd-id=kubeflow-pipelines" \
		--for condition=Ready --timeout=180s -n kubeflow 2>/dev/null || \
		printf "$(YELLOW)Some pods may still be starting — check with: make kfp-dev-status\n$(NC)"
	@kubectl port-forward -n kubeflow svc/ml-pipeline-ui "$(KFP_LOCAL_PORT):80" >/dev/null 2>&1 & echo $$! > "$(KFP_PID_FILE)"
	@sleep 2
	@printf "$(GREEN)KFP UI:  http://localhost:$(KFP_LOCAL_PORT)\n$(NC)"
	@printf "$(GREEN)Run:     make kfp-run NB=... KFP_HOST=http://localhost:$(KFP_LOCAL_PORT)\n$(NC)"

kfp-dev-stop: ## Stop port-forward and pause cluster (preserves all data)
	@if [ -f "$(KFP_PID_FILE)" ]; then \
		kill $$(cat "$(KFP_PID_FILE)") 2>/dev/null || true; \
		rm -f "$(KFP_PID_FILE)"; \
		printf "$(GREEN)Port-forward stopped\n$(NC)"; \
	fi
	@k3d cluster stop $(KFP_CLUSTER_NAME) 2>/dev/null || true
	@printf "$(GREEN)Cluster paused. Run 'make kfp-dev-start' to resume.\n$(NC)"

kfp-dev-delete: ## Delete cluster and free all resources (irreversible)
	@printf "$(YELLOW)Deleting cluster '$(KFP_CLUSTER_NAME)' and all KFP data...\n$(NC)"
	@if [ -f "$(KFP_PID_FILE)" ]; then \
		kill $$(cat "$(KFP_PID_FILE)") 2>/dev/null || true; \
		rm -f "$(KFP_PID_FILE)"; \
	fi
	@k3d cluster delete $(KFP_CLUSTER_NAME) 2>/dev/null || true
	@printf "$(GREEN)Cluster deleted. Run 'make kfp-dev-setup' to start fresh.\n$(NC)"

kfp-dev-status: ## Show cluster and KFP pod status
	@printf "$(BLUE)k3d clusters:\n$(NC)"
	@k3d cluster list 2>/dev/null || printf "$(YELLOW)k3d not installed\n$(NC)"
	@printf "\n$(BLUE)KFP pods (kubeflow namespace):\n$(NC)"
	@kubectl get pods -n kubeflow 2>/dev/null || printf "$(YELLOW)Cluster not running or unreachable\n$(NC)"

##@ Cleanup

clean: ## Clean all build artifacts
	@printf "$(BLUE)Cleaning...\n$(NC)"
	rm -rf .venv
	rm -rf dist *.egg-info
	rm -rf labextension/lib labextension/node_modules
	rm -rf jupyterlab_kubeflow_kale/labextension
	rm -rf .kfp-wheels .kale
	rm -f $(KFP_PID_FILE)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@printf "$(GREEN)Clean complete\n$(NC)"

clean-venv: ## Remove virtual environment only
	rm -rf .venv

##@ Lockfile Management

lock: check-uv ## Update uv.lock
	$(UV) lock

lock-upgrade: check-uv ## Upgrade all dependencies and update lock
	$(UV) lock --upgrade

##@ Development Helpers

jupyter: ## Start JupyterLab
	$(UV) run jupyter lab

jupyter-kfp: ## Start JupyterLab with KFP dev environment (run kfp-serve first!)
	@printf "$(YELLOW)Make sure 'make kfp-serve' is running in another terminal\n$(NC)"
	KALE_PIP_INDEX_URLS="http://$(KFP_HOST_ADDR):$(KFP_PORT)" \
	KALE_PIP_TRUSTED_HOSTS="$(KFP_HOST_ADDR)" \
	$(UV) run jupyter lab

watch-labextension: ## Watch labextension for changes (run in separate terminal)
	cd labextension && $(JLPM) watch

##@ Documentation

docs: ## Build the documentation site (HTML)
	@printf "$(BLUE)Building documentation...\n$(NC)"
	$(UV) sync --extra docs
	$(UV) run sphinx-build -b html docs/source docs/_build/html
	@printf "$(GREEN)Docs built: docs/_build/html/index.html\n$(NC)"

docs-serve: docs ## Build and serve the docs locally on port 8000
	@printf "$(BLUE)Serving docs on http://localhost:8000\n$(NC)"
	cd docs/_build/html && python3 -m http.server 8000

docs-clean: ## Remove built documentation
	rm -rf docs/_build

##@ Release

check-versions: ## Verify backend and labextension versions match
	@PY_VERSION=$$($(UV) run python -c "import re; m = re.search(r'__version__\s*=\s*\"([^\"]+)\"', open('kale/__init__.py').read()); print(m.group(1))"); \
	NPM_VERSION=$$(node -p "require('./labextension/package.json').version"); \
	PY_AS_SEMVER=$$(echo "$$PY_VERSION" | sed -E 's/([0-9]+\.[0-9]+\.[0-9]+)(a)([0-9]+)/\1-alpha.\3/; s/([0-9]+\.[0-9]+\.[0-9]+)(b)([0-9]+)/\1-beta.\3/; s/([0-9]+\.[0-9]+\.[0-9]+)(rc)([0-9]+)/\1-rc.\3/'); \
	if [ "$$PY_AS_SEMVER" != "$$NPM_VERSION" ]; then \
		printf "$(YELLOW)Version mismatch!\n$(NC)"; \
		printf "  Python (PEP 440):  $$PY_VERSION\n"; \
		printf "  Python (as semver): $$PY_AS_SEMVER\n"; \
		printf "  npm (semver):      $$NPM_VERSION\n"; \
		exit 1; \
	fi; \
	printf "$(GREEN)Versions match: $$PY_VERSION (Python) == $$NPM_VERSION (npm)\n$(NC)"

verify: lint test check-versions ## Run all checks (lint + test + version check)

release: ## Set release version (usage: make release VERSION=X.Y.Z)
	@test -n "$(VERSION)" || { printf "$(YELLOW)Usage: make release VERSION=X.Y.Za1\n$(NC)"; exit 1; }
	@# Validate PEP 440 version format
	@echo "$(VERSION)" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(a[0-9]+|b[0-9]+|rc[0-9]+)?$$' || { \
		printf "$(YELLOW)Invalid version format: $(VERSION)\n$(NC)"; \
		printf "$(YELLOW)Expected: X.Y.Z, X.Y.Za1, X.Y.Zb1, or X.Y.Zrc1\n$(NC)"; \
		exit 1; \
	}
	@# Update version
	python3 -c "import re; p='kale/__init__.py'; t=open(p).read(); open(p,'w').write(re.sub(r'__version__ = \".*\"', '__version__ = \"$(VERSION)\"', t))"
	@# Convert PEP 440 to semver for package.json
	@NPM_VERSION=$$(echo "$(VERSION)" | sed -E 's/([0-9]+\.[0-9]+\.[0-9]+)(a)([0-9]+)/\1-alpha.\3/; s/([0-9]+\.[0-9]+\.[0-9]+)(b)([0-9]+)/\1-beta.\3/; s/([0-9]+\.[0-9]+\.[0-9]+)(rc)([0-9]+)/\1-rc.\3/'); \
	cd labextension && npm version "$$NPM_VERSION" --no-git-tag-version --allow-same-version; \
	printf "$(GREEN)Version set to $(VERSION) (npm: $$NPM_VERSION)\n$(NC)"
	@# Generate changelog if git-cliff is available.
	@# Scope it to the X.Y line this version belongs to: start from the newest
	@# reachable tag outside that line, so CHANGELOG-X.Y.md accumulates every
	@# X.Y release and nothing older. --merged HEAD keeps tags cut on other
	@# release branches out of the range. Without a range git-cliff emits the
	@# whole project history, and without --tag the new entries land under an
	@# "[unreleased]" heading - both end up verbatim in the GitHub release body
	@# (see the github-release job in .github/workflows/release.yml).
	@if ! command -v git-cliff >/dev/null 2>&1; then \
		printf "$(YELLOW)git-cliff not found, skipping changelog generation\n$(NC)"; \
	else \
		MAJOR=$$(echo "$(VERSION)" | cut -d. -f1); \
		MINOR=$$(echo "$(VERSION)" | cut -d. -f2); \
		OUT=CHANGELOG/CHANGELOG-$$MAJOR.$$MINOR.md; \
		BASE=$$(git tag --list 'v[0-9]*' --merged HEAD --sort=-v:refname \
			| grep -v "^v$$MAJOR\.$$MINOR\." | head -1); \
		if [ -n "$$BASE" ]; then \
			git-cliff "$$BASE..HEAD" --tag v$(VERSION) --output $$OUT; \
			printf "$(GREEN)Changelog generated: $$OUT ($$BASE..HEAD, tagged v$(VERSION))\n$(NC)"; \
		else \
			git-cliff --tag v$(VERSION) --output $$OUT; \
			printf "$(GREEN)Changelog generated: $$OUT (full history, tagged v$(VERSION))\n$(NC)"; \
		fi; \
	fi

##@ Docker

DOCKER_IMAGE ?= kubeflow-kale
DOCKER_TAG ?= dev
KFP_HOST ?= http://host.docker.internal:8080

docker-build: build ## Build Docker image with Kale pre-installed
	@printf "$(BLUE)Building Docker image $(DOCKER_IMAGE):$(DOCKER_TAG)...\n$(NC)"
	docker build -f docker/Dockerfile -t $(DOCKER_IMAGE):$(DOCKER_TAG) .
	@printf "$(GREEN)Image built: $(DOCKER_IMAGE):$(DOCKER_TAG)\n$(NC)"

docker-run: ## Run Kale in Docker (JupyterLab on http://localhost:8888)
	@printf "$(YELLOW)Requires: kubectl port-forward -n kubeflow svc/ml-pipeline-ui 8080:8080\n$(NC)"
	@printf "$(YELLOW)Requires: make kfp-serve (in another terminal)\n$(NC)"
	@printf "$(BLUE)Starting $(DOCKER_IMAGE):$(DOCKER_TAG) on http://localhost:8888\n$(NC)"
	docker run --rm -p 8888:8888 \
		--add-host=host.docker.internal:host-gateway \
		-e KF_PIPELINES_ENDPOINT=$(KFP_HOST) \
		-e KF_PIPELINES_UI_ENDPOINT=http://localhost:8080 \
		-e KALE_PIP_INDEX_URLS=http://$(KFP_HOST_ADDR):$(KFP_PORT) \
		-e KALE_PIP_TRUSTED_HOSTS=$(KFP_HOST_ADDR) \
		$(DOCKER_IMAGE):$(DOCKER_TAG)

podman-run: ## Run Kale with Podman (JupyterLab on http://localhost:8888)
	@printf "$(YELLOW)Requires: kubectl port-forward -n kubeflow svc/ml-pipeline-ui 8080:8080\n$(NC)"
	@printf "$(YELLOW)Requires: make kfp-serve (in another terminal)\n$(NC)"
	@printf "$(BLUE)Starting $(DOCKER_IMAGE):$(DOCKER_TAG) on http://localhost:8888\n$(NC)"
	podman run --rm \
		--network=host \
		-e KF_PIPELINES_ENDPOINT=$(KFP_HOST) \
		-e KF_PIPELINES_UI_ENDPOINT=http://localhost:8080 \
		-e KALE_PIP_INDEX_URLS=http://$(KFP_HOST_ADDR):$(KFP_PORT) \
		-e KALE_PIP_TRUSTED_HOSTS=$(KFP_HOST_ADDR) \
		$(DOCKER_IMAGE):$(DOCKER_TAG)
