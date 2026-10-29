#!/usr/bin/env bash
# Copyright 2026 The Kubeflow Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -euo pipefail

ACTION="${1:?Usage: kfp-wheel-server.sh check|stop|start WHEEL_DIR PORT}"
WHEEL_DIR="${2:?Missing wheel directory}"
PORT="${3:?Missing port}"

WHEEL_DIR="$(realpath "$WHEEL_DIR")"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ID="$(printf '%s' "$REPO_ROOT" | cksum | awk '{print $1}')"
PID_FILE="/tmp/kale-kfp-wheel-server-${REPO_ID}.pid"
LOG_FILE="/tmp/kale-kfp-wheel-server-${REPO_ID}.log"

is_managed_server() {
    local pid="$1"
    local cwd
    local -a argv

    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    [[ -r "/proc/$pid/cmdline" && -e "/proc/$pid/cwd" ]] || return 1

    mapfile -d '' -t argv < "/proc/$pid/cmdline" || return 1
    cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null)" || return 1

    [[ "$cwd" == "$WHEEL_DIR" ]] &&
        [[ "${argv[1]-}" == "-m" ]] &&
        [[ "${argv[2]-}" == "http.server" ]] &&
        [[ "${argv[3]-}" == "$PORT" ]]
}

port_is_busy() {
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1
}

managed_pid() {
    [[ -f "$PID_FILE" ]] || return 1

    local pid
    pid="$(cat "$PID_FILE")"

    if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$PID_FILE"
        return 1
    fi

    if ! is_managed_server "$pid"; then
        echo "Error: PID file exists, but its process cannot be verified as this wheel server." >&2
        echo "Refusing to stop or overwrite an unverified process: $pid" >&2
        return 2
    fi

    printf '%s\n' "$pid"
}

case "$ACTION" in
    check)
        if managed_pid >/dev/null; then
            echo "Managed wheel server found."
        else
            status=$?
            [[ "$status" -ne 2 ]] || exit "$status"
            if port_is_busy; then
                echo "Error: port $PORT is occupied by an unmanaged process." >&2
                exit 1
            fi
            echo "Wheel server port $PORT is available."
        fi
        ;;

    stop)
        pid="$(managed_pid)" || {
            status=$?
            [[ "$status" -ne 2 ]] || exit "$status"
            if port_is_busy; then
                echo "Error: port $PORT is occupied by an unmanaged process." >&2
                exit 1
            fi
            echo "No managed wheel server to stop."
            exit 0
        }

        echo "Stopping managed wheel server (PID $pid)..."
        kill "$pid"

        for _ in {1..10}; do
            kill -0 "$pid" 2>/dev/null || break
            is_managed_server "$pid" || break
            sleep 1
        done

        if kill -0 "$pid" 2>/dev/null && is_managed_server "$pid"; then
            echo "Error: wheel server did not stop within 10 seconds." >&2
            exit 1
        fi

        rm -f "$PID_FILE"

        if port_is_busy; then
            echo "Error: port $PORT remains occupied; refusing to rebuild wheels." >&2
            exit 1
        fi
        ;;

    start)
        [[ -d "$WHEEL_DIR" ]] || {
            echo "Error: wheel directory does not exist: $WHEEL_DIR" >&2
            exit 1
        }

        if managed_pid >/dev/null; then
            echo "Error: managed wheel server is already running." >&2
            exit 1
        else
            status=$?
            [[ "$status" -ne 2 ]] || exit "$status"
        fi

        if port_is_busy; then
            echo "Error: port $PORT is occupied; refusing to start." >&2
            exit 1
        fi

        echo "Starting wheel server on port $PORT..."
        (
            cd "$WHEEL_DIR"
            nohup python3 -m http.server "$PORT" \
                >"$LOG_FILE" 2>&1 </dev/null &
            echo "$!" >"$PID_FILE"
        )

        ready=0
        for _ in {1..10}; do
            if managed_pid >/dev/null &&
                curl -sf "http://127.0.0.1:$PORT/kubeflow-kale/" >/dev/null; then
                ready=1
                break
            fi
            sleep 1
        done

        if [[ "$ready" -ne 1 ]]; then
            echo "Error: wheel server did not become ready. Log: $LOG_FILE" >&2
            echo "Attempting to clean up the failed startup..." >&2
            bash "$0" stop "$WHEEL_DIR" "$PORT" || true
            exit 1
        fi

        echo "Wheel server is ready."
        ;;

    *)
        echo "Usage: $0 check|stop|start WHEEL_DIR PORT" >&2
        exit 2
        ;;
esac