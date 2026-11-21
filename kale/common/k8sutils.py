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

import kubernetes

_k8s_watch = None
_api_client = None
_api_v1_client = None
_k8s_co_client = None


def _load_config():
    try:
        kubernetes.config.load_incluster_config()
    except kubernetes.config.ConfigException:  # Not in a notebook server
        try:
            kubernetes.config.load_kube_config()
        # FIXME: `kubernetes` raises a TypeError when a `config` file is not
        #  found. This is fixed starting from version `11.0.0`, which raises
        #  the correct `ConfigException`. We cannot yet upgrade the package
        #  because `kfserving` relies on `kubernetes==10.0.1`
        except TypeError:
            raise kubernetes.config.ConfigException(
                "Invalid kube-config file. No configuration found."
            )


def get_v1_client():
    """Get the Kubernetes V1 ApiClient."""
    global _api_client
    global _api_v1_client
    if not _api_client:
        _load_config()
        _api_client = kubernetes.client.ApiClient()
    if not _api_v1_client:
        _api_v1_client = kubernetes.client.CoreV1Api(_api_client)
    return _api_v1_client


def get_co_client():
    """Get the K8s client to interact with the custom objects API."""
    global _k8s_co_client
    if not _k8s_co_client:
        _load_config()
        _k8s_co_client = kubernetes.client.CustomObjectsApi()
    return _k8s_co_client


def get_pvc_access_modes(pvc_name: str, namespace: str) -> list[str]:
    """Return the access modes of a PVC, or an empty list on any error.

    This is intentionally best-effort: callers (the UI RPC and the runtime
    warning emitted into each pipeline step) must not fail if the service
    account lacks ``get`` permission on PVCs or the cluster is unreachable.

    Args:
        pvc_name: Name of the PersistentVolumeClaim to inspect.
        namespace: Kubernetes namespace to look in.

    Returns:
        A list of access mode strings, e.g. ``["ReadWriteOnce"]``, or ``[]``
        when the PVC cannot be fetched for any reason.
    """
    try:
        pvc = get_v1_client().read_namespaced_persistent_volume_claim(pvc_name, namespace)
        return list(pvc.spec.access_modes or [])
    except Exception:
        return []


def annotate_object(group, version, plural, name, namespace, annotations):
    """Annotate a custom Kubernetes object."""
    patch = {
        "apiVersion": f"{group}/{version}",
        "metadata": {"name": name, "annotations": annotations},
    }
    k8s_client = get_co_client()
    k8s_client.patch_namespaced_custom_object(group, version, namespace, plural, name, patch)
