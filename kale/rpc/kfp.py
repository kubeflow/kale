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

import functools
import logging
import os

import requests.exceptions
import urllib3.exceptions

from kale.common import kfp_client_factory, kfputils
from kale.rpc.errors import RPCServiceUnavailableError
from kale.rpc.log import KALE_LOG_FILE

log = logging.getLogger(__name__)

KALE_UPLOAD_LINK_ENV = "KALE_UPLOAD_LINK"
KALE_RUN_LINK_ENV = "KALE_RUN_LINK"

# Errors raised by the KFP client (directly, or via urllib3/requests under
# the hood) when the KFP API server cannot be reached at all, e.g. because
# the configured host is wrong or the server is down.
_KFP_CONNECTION_ERRORS = (
    urllib3.exceptions.MaxRetryError,
    requests.exceptions.ConnectionError,
)


def _handle_unreachable_kfp(func):
    """Turn KFP connection failures into a friendly, actionable RPC error."""

    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        except _KFP_CONNECTION_ERRORS:
            request.log.exception(
                "RPC function '%s' failed because KFP is not reachable", func.__name__
            )
            raise RPCServiceUnavailableError(
                message="KFP is not reachable.",
                # The frontend prefers showing `details` over `message` alone,
                # so repeat the headline here to keep the dialog self-contained.
                details=(
                    "KFP is not reachable. You can still compile notebooks, "
                    "but you cannot upload or run pipelines. You can find "
                    f"more information under {KALE_LOG_FILE}"
                ),
                trans_id=request.trans_id,
            )

    return wrapper


def _get_client(host=None):
    """Get a KFP client using saved configuration."""
    return kfp_client_factory.get_kfp_client(host=host)


def ping(request):
    # Intentionally not decorated with `_handle_unreachable_kfp`: this is the
    # reachability probe itself, and it already reports an unreachable server
    # by returning False rather than by raising.
    try:
        c = _get_client()
        c.get_kfp_healthz()
        return True
    except Exception:
        return False


@_handle_unreachable_kfp
def list_experiments(request):
    """List Kubeflow Pipelines experiments."""
    c = _get_client()
    experiments = [
        {"name": e.display_name, "id": e.experiment_id}
        for e in c.list_experiments().experiments or []
    ]
    return experiments


@_handle_unreachable_kfp
def get_ui_host(request):
    """Get a UI Host. If it does not exist return None."""
    c = _get_client()
    host = getattr(c, "_uihost", None) or getattr(c, "host", None)
    return host


def _validate_link(value, env_var):
    """Return value if it starts with http:// or https://, otherwise warns and return ''."""
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        log.warning(
            "%s is set but does not start with http:// or https:// "
            "(got: %r) — ignoring and using the default KFP UI links.",
            env_var,
            value,
        )
        return ""
    return value


def get_custom_links(request):
    """Get custom link patterns from environment variables.

    Returns a dict with 'upload' and 'run' keys. Values are the URL
    patterns if set and valid, or empty strings if not configured or invalid.

    Placeholders:
    - Upload: {pipeline_id}, {version_id}, {namespace}
    - Run: {run_id}, {namespace}
    """
    return {
        "upload": _validate_link(os.environ.get(KALE_UPLOAD_LINK_ENV, ""), KALE_UPLOAD_LINK_ENV),
        "run": _validate_link(os.environ.get(KALE_RUN_LINK_ENV, ""), KALE_RUN_LINK_ENV),
    }


@_handle_unreachable_kfp
def get_experiment(request, experiment_name):
    """Get a KFP experiment. If it does not exist return None."""
    client = _get_client()
    try:
        experiment = client.get_experiment(experiment_name=experiment_name)
    except ValueError as e:
        err_msg = f"No experiment is found with name {experiment_name}"
        if err_msg in str(e):
            return None
        else:
            # Unexpected exception
            raise
    except TypeError as e:
        # In case the installed KFP client does not contain the following fix:
        # https://github.com/kubeflow/pipelines/pull/4177
        err_msg = "'NoneType' object is not iterable"
        if err_msg in str(e):
            return None
        raise
    return {"id": experiment.experiment_id, "name": experiment.display_name}


@_handle_unreachable_kfp
def create_experiment(request, experiment_name, raise_if_exists=False):
    """Create a new experiment."""
    client = _get_client()
    exp = get_experiment(request, experiment_name)
    if not exp:
        experiment = client.create_experiment(name=experiment_name)
        return {"id": experiment.experiment_id, "name": experiment.display_name}
    if raise_if_exists:
        raise ValueError("Failed to create experiment, experiment already exists.")


@_handle_unreachable_kfp
def upload_pipeline(request, pipeline_package_path, pipeline_metadata):
    """Upload a KFP package as a new pipeline."""
    pipeline_name = pipeline_metadata["pipeline_name"]
    pid, vid = kfputils.upload_pipeline(pipeline_package_path, pipeline_name)
    return {"pipeline": {"pipelineid": pid, "versionid": vid, "name": pipeline_name}}


@_handle_unreachable_kfp
def run_pipeline(request, pipeline_metadata, pipeline_id, version_id, pipeline_package_path):
    """Run a pipeline."""
    run = kfputils.run_pipeline(
        experiment_name=pipeline_metadata["experiment_name"],
        pipeline_id=pipeline_id,
        version_id=version_id,
        pipeline_package_path=pipeline_package_path,
    )

    return {"id": run.run_id, "name": run.run_info.display_name, "status": run.run_info.state}


@_handle_unreachable_kfp
def get_run(request, run_id):
    """Get an existing run's details."""
    client = _get_client()
    run = client.get_run(run_id)
    return {"id": run.run_id, "name": run.display_name, "status": run.state}
