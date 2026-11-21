#!/usr/bin/env bash
# Copyright 2026 The Kubeflow Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Sets up a lightweight KFP standalone cluster using k3d (k3s in Docker).
# Requires: docker, kubectl. k3d is installed automatically if missing.
#
# Usage: bash scripts/kfp-dev-setup.sh [cluster-name] [kfp-version] [local-port] [pid-file]

set -euo pipefail

COMMAND="${1:-setup}"   # setup | upgrade
CLUSTER_NAME="${2:-kale-kfp}"
KFP_VERSION="${3:-2.16.0}"
LOCAL_PORT="${4:-8080}"
PID_FILE="${5:-.kfp-dev-pf.pid}"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${BLUE}%s${NC}\n" "$*"; }
ok()    { printf "${GREEN}%s${NC}\n" "$*"; }
warn()  { printf "${YELLOW}%s${NC}\n" "$*"; }
die()   { printf "${RED}ERROR: %s${NC}\n" "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

check_prereqs() {
    local missing=()
    command -v docker  >/dev/null 2>&1 || missing+=(docker)
    command -v kubectl >/dev/null 2>&1 || missing+=(kubectl)

    if [ ${#missing[@]} -gt 0 ]; then
        die "Missing required tools: ${missing[*]}. Install them and re-run."
    fi

    if ! docker info >/dev/null 2>&1; then
        die "Docker daemon is not running. Start Docker and re-run."
    fi
}

ensure_k3d() {
    if command -v k3d >/dev/null 2>&1; then
        ok "k3d already installed ($(k3d version | head -1))"
        return
    fi

    warn "k3d not found — installing via official install script..."
    curl -fsSL https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
    ok "k3d installed"
}

# ---------------------------------------------------------------------------
# Cluster
# ---------------------------------------------------------------------------

create_cluster() {
    if k3d cluster list 2>/dev/null | grep -q "^${CLUSTER_NAME}[[:space:]]"; then
        warn "Cluster '${CLUSTER_NAME}' already exists — skipping creation."
        info "Starting cluster in case it was stopped..."
        k3d cluster start "${CLUSTER_NAME}"
    else
        info "Creating k3d cluster '${CLUSTER_NAME}'..."
        info "(Traefik ingress is disabled to save memory — KFP is accessed via port-forward)"
        k3d cluster create "${CLUSTER_NAME}" \
            --agents 1 \
            --k3s-arg "--disable=traefik@server:0" \
            --wait
        ok "Cluster '${CLUSTER_NAME}' created"
    fi

    info "Switching kubectl context to k3d-${CLUSTER_NAME}..."
    kubectl config use-context "k3d-${CLUSTER_NAME}"
    ok "kubectl context set to k3d-${CLUSTER_NAME}"
}

# ---------------------------------------------------------------------------
# KFP deployment
# ---------------------------------------------------------------------------

_apply_kfp_manifests() {
    info "  [1/3] Applying cluster-scoped resources..."
    kubectl apply -k \
        "github.com/kubeflow/pipelines/manifests/kustomize/cluster-scoped-resources?ref=${KFP_VERSION}"

    info "  [2/3] Waiting for CRDs to be established..."
    kubectl wait crd/applications.app.k8s.io \
        --for condition=established \
        --timeout=60s

    info "  [3/3] Applying platform-agnostic KFP manifest..."
    kubectl apply -k \
        "github.com/kubeflow/pipelines/manifests/kustomize/env/platform-agnostic?ref=${KFP_VERSION}"

    info "  Waiting for KFP pods to be Ready (up to 5 min — images are being pulled)..."
    kubectl wait pods \
        -l "application-crd-id=kubeflow-pipelines" \
        --for condition=Ready \
        --timeout=300s \
        -n kubeflow
}

deploy_kfp() {
    if kubectl get namespace kubeflow >/dev/null 2>&1 && \
       kubectl get deploy -n kubeflow ml-pipeline >/dev/null 2>&1; then
        warn "KFP already deployed in namespace 'kubeflow' — skipping."
        warn "To upgrade KFP to v${KFP_VERSION}, run: make kfp-dev-upgrade"
        return
    fi

    info "Deploying KFP v${KFP_VERSION} (platform-agnostic, no Argo/Docker executor)..."
    _apply_kfp_manifests
    ok "KFP v${KFP_VERSION} deployed"
}

upgrade_kfp() {
    info "Upgrading KFP to v${KFP_VERSION} on cluster '${CLUSTER_NAME}'..."
    info "Switching kubectl context to k3d-${CLUSTER_NAME}..."
    kubectl config use-context "k3d-${CLUSTER_NAME}"
    _apply_kfp_manifests
    ok "KFP upgraded to v${KFP_VERSION}"
}

# ---------------------------------------------------------------------------
# Port-forward
# ---------------------------------------------------------------------------

start_port_forward() {
    # Stop only the port-forward process recorded by this workflow.
    if [[ -f "${PID_FILE}" ]]; then
        OLD_PID="$(cat "${PID_FILE}")"
        if [[ "${OLD_PID}" =~ ^[0-9]+$ ]]; then
            kill "${OLD_PID}" 2>/dev/null || true
        fi
        rm -f "${PID_FILE}"
    fi

    info "Starting port-forward: localhost:${LOCAL_PORT} → kubeflow/ml-pipeline-ui:80"

    PF_LOG="/tmp/kale-kfp-port-forward.log"

    nohup kubectl port-forward \
        -n kubeflow \
        svc/ml-pipeline-ui \
        "${LOCAL_PORT}:80" \
        >"${PF_LOG}" 2>&1 < /dev/null &

    PF_PID=$!
    echo "${PF_PID}" > "${PID_FILE}"

    info "Port-forward process started with PID ${PF_PID}"

# Wait until the port-forward is actually ready.
    for _ in $(seq 1 15); do
        if curl -sf --max-time 2 \
            "http://localhost:${LOCAL_PORT}/apis/v2beta1/healthz" \
            >/dev/null 2>&1; then
            ok "Port-forward verified and KFP API is healthy"
            return
        fi
        sleep 1
    done

    warn "Port-forward did not become ready within 15 seconds."
    warn "Check the log with: cat ${PF_LOG}"
    warn "Check status with: make kfp-dev-status"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
    case "${COMMAND}" in
        upgrade)
            echo ""
            info "======================================================="
            info " Kale KFP upgrade"
            info " Cluster: ${CLUSTER_NAME}  |  KFP: v${KFP_VERSION}"
            info "======================================================="
            echo ""
            check_prereqs
            upgrade_kfp
            echo ""
            ok "KFP upgraded to v${KFP_VERSION} on cluster '${CLUSTER_NAME}'."
            echo ""
            ;;
        setup|*)
            echo ""
            info "======================================================="
            info " Kale KFP dev cluster setup"
            info " Cluster: ${CLUSTER_NAME}  |  KFP: v${KFP_VERSION}"
            info "======================================================="
            echo ""
            check_prereqs
            ensure_k3d
            create_cluster
            deploy_kfp
            start_port_forward
            echo ""
            ok "======================================================="
            ok " KFP dev cluster is ready!"
            ok "======================================================="
            printf "${BLUE} UI:     ${NC}http://localhost:${LOCAL_PORT}\n"
            printf "${BLUE} Compile:${NC} make kfp-compile NB=notebook.ipynb\n"
            printf "${BLUE} Run:    ${NC} make kfp-run NB=notebook.ipynb KFP_HOST=http://localhost:${LOCAL_PORT}\n"
            printf "${BLUE} Stop:   ${NC} make kfp-dev-stop\n"
            printf "${BLUE} Resume: ${NC} make kfp-dev-start\n"
            printf "${BLUE} Upgrade:${NC} make kfp-dev-upgrade\n"
            printf "${BLUE} Delete: ${NC} make kfp-dev-delete\n"
            echo ""
            warn "Memory tip: if Docker is slow, increase Docker Desktop memory in Settings → Resources."
            warn "KFP requires ~2 GB. k3d overhead is ~512 MB on top of that."
            echo ""
            ;;
    esac
}

main
