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

import glob
import hashlib
import importlib.util
import json
import logging
import os
import re
from shutil import copyfile
import tempfile
import time
from typing import Any

import kfp
from kfp_server_api.exceptions import ApiException

from kale.common import kfp_client_factory, utils

KFP_RUN_ID_LABEL_KEY = "pipeline/runid"
KFP_RUN_NAME_ANNOTATION_KEY = "pipelines.kubeflow.org/run_name"
KFP_COMPONENT_SPEC_ANNOTATION_KEY = "pipelines.kubeflow.org/component_spec"
KFP_SWF_NAME_ANNOTATION_KEY = "scheduledworkflows.kubeflow.org/scheduledWorkflowName"
KFP_RUN_FINAL_STATES = ["Succeeded", "Skipped", "Failed", "Error"]
KFP_UI_METRICS_FILE_PATH = "/tmp/mlpipeline-metrics.json"

_logger = None

log = logging.getLogger(__name__)


def get_pipeline_id(pipeline_name: str, host: str = None) -> str:
    """List through the existing pipelines and filter by pipeline name.

    Args:
        pipeline_name: name of the pipeline
        host: custom host when executing outside of the cluster

    Returns:
        The matching pipeline id. None if not found
    """
    client = kfp_client_factory.get_kfp_client(host)
    token = ""
    pipeline_id = None
    while pipeline_id is None and token is not None:
        pipelines = client.list_pipelines(page_token=token)
        token = pipelines.next_page_token
        f = next(
            filter(lambda x: x.display_name == pipeline_name, pipelines.pipelines or []),
            None,
        )
        if f is not None:
            pipeline_id = f.pipeline_id
    return pipeline_id


def get_pipeline_version_id(version_name: str, pipeline_id: str, host: str = None) -> str:
    """List through the versions and filter by version name.

    Args:
        version_name: name of the version
        pipeline_id: ID of the pipeline
        host: custom host when executing outside of the cluster

    Returns:
        The matching pipeline id. None if not found
    """
    client = kfp_client_factory.get_kfp_client(host)
    page_token = ""
    version_id = None
    while version_id is None and page_token is not None:
        versions = client.pipelines.list_pipeline_versions(
            resource_key_type="PIPELINE",
            resource_key_id=pipeline_id,
            page_token=page_token,
        )
        page_token = versions.next_page_token
        f = next(filter(lambda x: x.name == version_name, versions.versions), None)
        if f is not None:
            version_id = f.id
    return version_id


def compile_pipeline(pipeline_source: str, pipeline_name: str) -> str:
    """Read in the generated python script and compile it to a KFP package."""
    # create a tmp folder
    tmp_dir = tempfile.mkdtemp()
    # copy generated script to temp dir
    copyfile(pipeline_source, tmp_dir + "/" + "pipeline_code.py")
    # a composed pipeline imports its per-notebook DSL modules, generated next
    # to it; carry those along so the script stays executable from the temp dir.
    # Only the generated modules, so an unrelated script left in the output
    # directory is never imported.
    from kale.compiler import MODULE_PREFIX  # imported here: compiler imports this module

    modules = os.path.join(os.path.dirname(pipeline_source), f"{MODULE_PREFIX}*.py")
    for sibling in glob.glob(modules):
        copyfile(sibling, os.path.join(tmp_dir, os.path.basename(sibling)))

    path = tmp_dir + "/" + "pipeline_code.py"
    spec = importlib.util.spec_from_file_location(tmp_dir.split("/")[-1], path)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)

    # path to generated pipeline package
    pipeline_package = os.path.join(
        os.path.dirname(pipeline_source), pipeline_name + ".pipeline.yaml"
    )
    kfp.compiler.Compiler().compile(foo.auto_generated_pipeline, pipeline_package)
    return pipeline_package


def upload_pipeline(
    pipeline_package_path: str, pipeline_name: str, host: str = None
) -> tuple[str, str]:
    """Upload pipeline package to KFP.

    If a pipeline with the provided name already exits, upload a new version.

    Args:
        pipeline_package_path: Path to .tar.gz kfp pipeline
        pipeline_name: Name of the uploaded pipeline
        host: custom host when executing outside of the cluster
    Returns: (pipeline_id, version_id)
    """
    client = kfp_client_factory.get_kfp_client(host)
    log.info("Uploading pipeline '%s'...", pipeline_name)
    pipeline_id = get_pipeline_id(pipeline_name, host=host)
    if not pipeline_id:
        # New pipeline: upload_pipeline creates a default version automatically
        upp = client.upload_pipeline(
            pipeline_package_path=pipeline_package_path, pipeline_name=pipeline_name
        )
        pipeline_id = upp.pipeline_id
        log.info("Uploaded pipeline '%s' with id: %s", pipeline_name, pipeline_id)
        # Get the default version that was created with the pipeline
        versions = client.list_pipeline_versions(pipeline_id=pipeline_id)
        version_id = versions.pipeline_versions[0].pipeline_version_id
    else:
        # Existing pipeline: upload a new version
        version_name = utils.random_string()
        upv = client.upload_pipeline_version(
            pipeline_package_path=pipeline_package_path,
            pipeline_version_name=version_name,
            pipeline_id=pipeline_id,
        )
        version_id = upv.pipeline_version_id
        log.info("Uploaded version '%s' for pipeline '%s'.", version_name, pipeline_name)
    return pipeline_id, version_id


def run_pipeline(
    experiment_name: str,
    pipeline_id: str,
    run_name: str = None,
    version_id: str = None,
    host: str = None,
    pipeline_package_path: str = None,
    **kwargs,
) -> Any:
    """Run pipeline (without uploading) in kfp.

    Args:
        run_name: The name of the kfp run (autogenerated if not provided)
        experiment_name: The name of the kfp experiment
        pipeline_id: The ID of the uploaded pipeline to be run
        version_id: the ID of the pipeline to be run
        host: custom host when executing outside of the cluster

    Returns:
        Pipeline run metadata
    """
    client = kfp_client_factory.get_kfp_client(host)
    log.info("Creating KFP experiment '%s'...", experiment_name)
    client.create_experiment(experiment_name)
    pipeline = client.get_pipeline(pipeline_id)
    pipeline_name = pipeline.display_name

    try:
        version_name = client.get_pipeline_version(
            pipeline_id=pipeline_id, pipeline_version_id=version_id
        ).display_name
    except Exception:
        log.debug(
            "Could not retrieve pipeline version with ID '%s'. Using 'unknown'.",
            version_id,
        )
        version_name = "unknown"

    if not run_name:
        run_name = f"{pipeline_name}-{version_name}-{utils.random_string()}"
    display_version = "({}version: '{}')".format("" if version_id else "default ", version_name)
    log.info(
        "Submitting new pipeline run '%s' for pipeline '%s' %s ...",
        run_name,
        pipeline_name,
        display_version,
    )

    try:
        run = client.create_run_from_pipeline_package(
            pipeline_file=pipeline_package_path,
            arguments=kwargs,
            run_name=run_name,
            experiment_name=experiment_name,
        )
    except ApiException as e:
        try:
            body = json.loads(e.body or "{}")

            if body.get("code") == 13:
                details = body.get("details") or []

                for d in details:
                    if (
                        d.get("@type") == "type.googleapis.com/google.rpc.Status"
                        and d.get("code") == 2
                    ):
                        message = body.get("message", "").lower()

                        if "failed to unmarshal kubernetes config" in message and re.search(
                            r"unknown field.*securitycontext",
                            message,
                            re.IGNORECASE,
                        ):
                            raise RuntimeError(
                                "Your KFP server does not support the 'securityContext' field. "
                                "Please upgrade Kubeflow Pipelines to version >= 2.16.0."
                            ) from e

        except (ValueError, TypeError):
            pass

        raise

    print("Pipeline submitted!")
    log.info("Run ID: %s", run.run_id)
    run_url = f"View: {host}/#/runs/details/{run.run_id}"
    log.info("Successfully submitted pipeline run.")
    log.info("Run URL: <host>%s", run_url)
    return run


def generate_mlpipeline_metrics(metrics):
    """Generate a KFP_UI_METRICS_FILE_PATH file.

    Args:
        metrics (dict): a dictionary where the key is the metric name and the
            value is its value.
    """
    try:
        with open(KFP_UI_METRICS_FILE_PATH, "w", encoding="utf-8") as _kale_mf:
            json.dump(metrics, _kale_mf)
    except (OSError, TypeError, PermissionError) as e:
        log.error("Not able to create metrics file, an unexpected error happened: %s", e)


def load_mlpipeline_metrics(output):
    """Loads the saved metrics into the provided Output metrics artifact.
    Args:
    output (Output[Metrics]): the Output artifact to load the metrics into.
    """
    if os.path.exists(KFP_UI_METRICS_FILE_PATH):
        with open(KFP_UI_METRICS_FILE_PATH, encoding="utf-8") as _kale_mf:
            _kale_kfp_metrics = json.load(_kale_mf)
            for _metric_name, _metric_value in _kale_kfp_metrics.items():
                output.log_metric(_metric_name, _metric_value)


def get_experiment_from_run_id(run_id: str):
    """Retrieve the experiment in which a run belongs.

    Returns: ApiExperiment - the KFP Experiment which owns the run
    """
    log.info("Getting experiment from run with ID '%s'...", run_id)
    client = kfp_client_factory.get_kfp_client()
    run = client.runs.get_run(run_id=run_id).run
    experiment_id = None
    type_experiment = client.api_models.ApiResourceType.EXPERIMENT
    relationship_owner = client.api_models.ApiRelationship.OWNER
    for ref in run.resource_references:
        if ref.relationship == relationship_owner and ref.key.type == type_experiment:
            experiment_id = ref.key.id
    # NOTE: It is safe to assume that a resource reference of type EXPERIMENT
    # exists, as well as an experiment with that ID
    log.info("Successfully retrieved experiment ID: %s", experiment_id)
    return client.experiments.get_experiment(id=experiment_id)


def get_run(run_id: str, host: str = None):
    """Retrieve KFP run based on RunID."""
    client = kfp_client_factory.get_kfp_client(host)
    return client.get_run(run_id)


def wait_kfp_run(run_id: str):
    """Wait for a KFP run to complete.

    Args:
        run_id: ID of the created KFP run

    Returns:
        status: Status of KFP run upon completion
    """
    log.info("Watching for Run with ID: '%s'", run_id)
    while True:
        time.sleep(30)
        run = get_run(run_id)
        status = run.run.status
        log.info("Run status: %s", status)
        if status not in KFP_RUN_FINAL_STATES:
            continue
        return status


def get_kfp_run_metrics(run_id: str):
    """Retrieve output metrics of a KFP run.

    We sleep() and try multiple times to make sure that the KFP persistence
    agent has reported run metrics.

    Args:
        run_id: ID of the created KFP run
    Returns:
        metrics: Dict of metrics along with their values
    """
    run_metrics = None
    max_tries = 3
    tries = 0
    while not run_metrics:
        if tries >= max_tries:
            return {}
        time.sleep(5)
        log.info("Try %d: Checking for run metrics...", tries)
        run = get_run(run_id=run_id)
        run_metrics = run.run.metrics
        tries += 1

    log.info("Found run metrics!")
    return {metric.name: metric.number_value for metric in run_metrics}


def get_workflow_from_run(run):
    """Get the workflow manifest from a KFP run object."""
    return json.loads(run.pipeline_runtime.workflow_manifest)


def format_kfp_run_id_uri(run_id: str):
    """Return a KFP run ID as a URI."""
    return f"kfp:run:{run_id}"


def compute_component_id(pod):
    """Compute unique component ID.

    Kale steps are KFP SDK Components. This is the way MetadataWriter generates
    unique names for such components.
    """
    log.info(
        "Computing component ID for pod %s/%s...",
        pod.metadata.namespace,
        pod.metadata.name,
    )
    component_spec_text = pod.metadata.annotations.get(KFP_COMPONENT_SPEC_ANNOTATION_KEY)
    if not component_spec_text:
        raise ValueError("KFP component spec annotation not found in pod")
    component_spec = json.loads(component_spec_text)
    component_spec_digest = hashlib.sha256(component_spec_text.encode()).hexdigest()
    component_name = component_spec.get("name")
    component_id = component_name + "@sha256=" + component_spec_digest
    log.info("Computed component ID: %s", component_id)
    return component_id
