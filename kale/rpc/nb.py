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
import shutil

from tabulate import tabulate

from kale import Compiler, NotebookProcessor, marshal
from kale.common import astutils, k8sutils, kfputils, kfutils, podutils
from kale.rpc.errors import RPCInternalError, RPCUnhandledError
from kale.rpc.log import create_adapter

KALE_MARSHAL_DIR_POSTFIX = ".kale.marshal.dir"
KALE_PIPELINE_STEP_ENV = "KALE_PIPELINE_STEP"

logger = create_adapter(logging.getLogger(__name__))


def resume_notebook_path(request, server_root=None):
    """Get the relative path of the notebook found in KALE_NOTEBOOK_PATH.

    server_root is the path to where the jupyter server is running
    (--notebook-dir path, if set, otherwise location of the `jupyter` was run)
    The path is not absolute, but starts with `~` if under HOME.
    """
    p = os.environ.get("KALE_NOTEBOOK_PATH")
    if p and not os.path.isfile(p):
        raise RuntimeError(f"env path KALE_NOTEBOOK_PATH={p} is not a file")
    if not p:
        return None

    home = os.environ.get("HOME")
    if not home.endswith("/"):
        home = home + "/"

    # JupyterLab needs a relative path to open a file. If server_root is not
    # defined, assume jupyter is running under HOME
    if server_root:
        server_root = os.path.expanduser(server_root)
        if not p.startswith(server_root):
            raise ValueError(
                f"Trying to resume a notebook from path {p}, but"
                f" the provided server root {server_root} does not match the"
                " notebook's path."
            )
        return p[len(server_root) :]
    elif p.startswith(home):
        return p[len(home) :]
    else:
        return p


def get_default_base_image_env(request):
    """Get ``KALE_DEFAULT_BASE_IMAGE`` when set, or an empty string."""
    from kale.common.utils import get_default_base_image_from_env

    return get_default_base_image_from_env() or ""


# fixme: Remove the debug argument from the labextension RPC call.
def compile_notebook(request, source_notebook_path, notebook_metadata_overrides=None, debug=False):
    """Compile the notebook to KFP DSL."""
    try:
        processor = NotebookProcessor(source_notebook_path, notebook_metadata_overrides)
        pipeline = processor.run()
        imports_and_functions = processor.get_imports_and_functions()
        script_path = Compiler(pipeline, imports_and_functions).compile()

        """FIXME: Why were we tapping into the Kale logger?
        instance = Kale(source_notebook_path,
        notebook_metadata_overrides, debug)
        instance.logger = request.log if
        hasattr(request, "log") else logger"""

        package_path = kfputils.compile_pipeline(script_path, pipeline.config.pipeline_name)

        with open(script_path) as f:
            script_content = f.read()

        return {
            "pipeline_package_path": os.path.relpath(package_path),
            "pipeline_metadata": pipeline.config.to_dict(),
            "script_content": script_content,
        }
    except ValueError as e:
        msg = str(e)
        request.log.exception("ValueError during notebook compilation: %s", msg)
        if "Task is missing from pipeline" in msg:
            # Provide guidance to the user about how to fix the issue.
            raise RPCUnhandledError(
                details=(
                    "The pipeline does not have any steps. "
                    "Please tag a cell as a pipeline step or set "
                    "`steps_defaults` in the notebook metadata."
                ),
                trans_id=request.trans_id,
            )
        raise RPCInternalError(details=msg, trans_id=request.trans_id)
    except Exception as e:
        # Let the run dispatcher handle generic exceptions as unhandled,
        # but log for debug purposes.
        request.log.exception("Unexpected error during notebook compilation: %s", e)
        raise


def validate_notebook(request, source_notebook_path, notebook_metadata_overrides=None):
    """Validate notebook metadata."""
    # Notebook metadata is validated at class instantiation
    NotebookProcessor(source_notebook_path, notebook_metadata_overrides)
    return True


def get_pipeline_parameters(request, source_notebook_path):
    """Get the pipeline parameters tagged in the notebook."""
    # read notebook
    log = request.log if hasattr(request, "log") else logger
    try:
        processor = NotebookProcessor(
            os.path.expanduser(source_notebook_path), skip_validation=True
        )
        params_source = processor.get_pipeline_parameters_source()
        if params_source == "":
            raise ValueError(
                "No pipeline parameters found. Please tag a cell"
                " of the notebook with the `pipeline-parameters`"
                " tag."
            )
        # get a dict from the 'pipeline parameters' cell source code
        params_dict = astutils.parse_assignments_expressions(params_source)
    except ValueError as e:
        log.exception("Value Error during parsing of pipeline parameters")
        raise RPCInternalError(details=str(e), trans_id=request.trans_id)
    # convert dict in list so its easier to parse in js
    params = [[k, *v] for k, v in params_dict.items()]
    log.info("Pipeline parameters:")
    for ln in tabulate(params, headers=["name", "type", "value"]).split("\n"):
        log.info(ln)
    return params


def get_pipeline_metrics(request, source_notebook_path):
    """Get the pipeline metrics tagged in the notebook."""
    # read notebook
    log = request.log if hasattr(request, "log") else logger
    try:
        processor = NotebookProcessor(
            os.path.expanduser(source_notebook_path), skip_validation=True
        )
        metrics_source = processor.get_pipeline_metrics_source()
        if metrics_source == "":
            raise ValueError(
                "No pipeline metrics found. Please tag a cell"
                " of the notebook with the `pipeline-metrics`"
                " tag."
            )
        # get a dict from the 'pipeline parameters' cell source code
        metrics = astutils.parse_metrics_print_statements(metrics_source)
    except ValueError as e:
        log.exception("Failed to parse pipeline metrics")
        raise RPCInternalError(details=str(e), trans_id=request.trans_id)
    log.info(f"Pipeline metrics: {metrics}")
    return metrics


def _get_kale_marshal_dir(source_notebook_path):
    nb_file_name = os.path.basename(source_notebook_path)
    nb_dir_name = os.path.dirname(source_notebook_path)
    kale_marshal_dir_name = f".{nb_file_name}{KALE_MARSHAL_DIR_POSTFIX}"
    return os.path.realpath(os.path.join(nb_dir_name, kale_marshal_dir_name))


def unmarshal_data(source_notebook_path):
    """Unmarshal data from the marshal directory."""
    source_notebook_path = os.path.expanduser(source_notebook_path)
    kale_marshal_dir = _get_kale_marshal_dir(source_notebook_path)
    if not os.path.exists(kale_marshal_dir):
        return {}

    marshal.set_data_dir(kale_marshal_dir)
    return {
        os.path.splitext(f)[0]: marshal.load(os.path.splitext(f)[0])
        for f in os.listdir(kale_marshal_dir)
    }


def explore_notebook(request, source_notebook_path):
    """Check if the notebook is to be resumed at a specific pipeline step."""
    source_notebook_path = os.path.expanduser(source_notebook_path)
    step_name = os.getenv(KALE_PIPELINE_STEP_ENV, None)
    kale_marshal_dir = _get_kale_marshal_dir(source_notebook_path)

    if step_name and os.path.exists(kale_marshal_dir):
        return {"is_exploration": True, "step_name": step_name}
    return {"is_exploration": False, "step_name": ""}


def remove_marshal_dir(request, source_notebook_path):
    """Remove the marshal directory."""
    source_notebook_path = os.path.expanduser(source_notebook_path)
    kale_marshal_dir = _get_kale_marshal_dir(source_notebook_path)
    if os.path.exists(kale_marshal_dir):
        shutil.rmtree(kale_marshal_dir)


def find_poddefault_labels_on_server(request):
    """Find server's labels that correspond to poddefaults applied."""
    old_logger = kfutils.log
    kfutils.log = request.log
    labels = kfutils.find_poddefault_labels()
    kfutils.log = old_logger
    return labels


def get_namespace(request):
    """Retrieve the namespace of the notebook."""
    request.log.info("Retrieving notebook's namespace...")
    namespace = podutils.get_namespace()
    request.log.info("Notebook's namespace is '%s'", namespace)
    return namespace


def list_pvcs(request):
    """List PersistentVolumeClaims available in the current namespace.

    Returns a sorted list of dicts with PVC info:
    ``{"name": <pvc-name>, "access_modes": ["ReadWriteOnce", ...]}``

    On any exception (e.g. no cluster access, missing service-account token)
    returns an empty list so the UI combobox degrades gracefully.
    """
    log = request.log if hasattr(request, "log") else logger
    try:
        namespace = podutils.get_namespace()
        pvc_list = k8sutils.get_v1_client().list_namespaced_persistent_volume_claim(namespace)
        pvcs = sorted(
            [
                {
                    "name": pvc.metadata.name,
                    "access_modes": list(pvc.spec.access_modes or []),
                }
                for pvc in pvc_list.items
            ],
            key=lambda p: p["name"],
        )
        log.info("Found %d PVC(s) in namespace '%s'", len(pvcs), namespace)
        return pvcs
    except Exception as e:
        log.warning("Could not list PVCs, returning empty list. Reason: %s", e)
        return []


def list_notebook_volumes(request):
    """List PVCs currently mounted on the notebook pod.

    Returns a sorted list of dicts:
    ``{"name": <pvc-name>, "mount_point": <path>, "access_modes": [...]}``

    Returns an empty list on any error so the UI dialog degrades gracefully.
    """
    log = request.log if hasattr(request, "log") else logger
    try:
        namespace = podutils.get_namespace()
        pod_name = podutils.get_pod_name()
        pod = podutils.get_pod(pod_name, namespace)

        pvc_by_vol_name = {}
        for vol in pod.spec.volumes or []:
            if vol.persistent_volume_claim:
                pvc_by_vol_name[vol.name] = vol.persistent_volume_claim.claim_name

        results = {}
        for container in pod.spec.containers or []:
            for mount in container.volume_mounts or []:
                if mount.name in pvc_by_vol_name and mount.name not in results:
                    pvc_name = pvc_by_vol_name[mount.name]
                    results[mount.name] = {
                        "name": pvc_name,
                        "mount_point": mount.mount_path,
                        "access_modes": k8sutils.get_pvc_access_modes(pvc_name, namespace),
                    }

        volumes = sorted(results.values(), key=lambda v: v["name"])
        log.info("Found %d PVC mount(s) on pod '%s'", len(volumes), pod_name)
        return volumes
    except Exception as e:
        log.warning("Could not list notebook pod volumes. Reason: %s", e)
        return []


def get_security_context_defaults(request):
    """Get security context defaults from environment variables.

    Returns a dict with security context settings read from KALE_SECURITY_CONTEXT_*
    environment variables. Only includes keys that were explicitly set via env vars;
    missing keys mean the caller should use their own defaults.
    """
    from kale.common.utils import get_security_context_from_env

    security_context = get_security_context_from_env()
    return security_context.to_dict()
