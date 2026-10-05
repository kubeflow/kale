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

import logging
import os

from kale.common import kfp_client_factory, kfputils

log = logging.getLogger(__name__)

KALE_UPLOAD_LINK_ENV = "KALE_UPLOAD_LINK"
KALE_RUN_LINK_ENV = "KALE_RUN_LINK"


def _get_client(host=None):
    """Get a KFP client using saved configuration."""
    return kfp_client_factory.get_kfp_client(host=host)


def ping(request):
    try:
        c = _get_client()
        c.get_kfp_healthz()
        return True
    except Exception:
        return False


def list_experiments(request):
    """List Kubeflow Pipelines experiments.

    Returns an empty list when KFP is unreachable so that the notebook-open
    flow degrades silently instead of surfacing a blocking error dialog.
    """
    try:
        c = _get_client()
        experiments = [
            {"name": exp.display_name, "id": exp.experiment_id}
            for exp in c.list_experiments().experiments or []
        ]
        return experiments
    except Exception as e:
        log.warning("KFP not reachable, returning empty experiments list: %s", e)
        return []


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


def create_experiment(request, experiment_name, raise_if_exists=False):
    """Create a new experiment."""
    client = _get_client()
    exp = get_experiment(None, experiment_name)
    if not exp:
        experiment = client.create_experiment(name=experiment_name)
        return {"id": experiment.experiment_id, "name": experiment.display_name}
    if raise_if_exists:
        raise ValueError("Failed to create experiment, experiment already exists.")


def upload_pipeline(request, pipeline_package_path, pipeline_metadata):
    """Upload a KFP package as a new pipeline."""
    pipeline_name = pipeline_metadata["pipeline_name"]
    pid, vid = kfputils.upload_pipeline(pipeline_package_path, pipeline_name)
    return {"pipeline": {"pipelineid": pid, "versionid": vid, "name": pipeline_name}}


def run_pipeline(request, pipeline_metadata, pipeline_id, version_id, pipeline_package_path):
    """Run a pipeline."""
    run = kfputils.run_pipeline(
        experiment_name=pipeline_metadata["experiment_name"],
        pipeline_id=pipeline_id,
        version_id=version_id,
        pipeline_package_path=pipeline_package_path,
    )

    return {"id": run.run_id, "name": run.run_info.display_name, "status": run.run_info.state}


def get_run(request, run_id):
    """Get an existing run's details."""
    client = _get_client()
    run = client.get_run(run_id)
    return {"id": run.run_id, "name": run.display_name, "status": run.state}
