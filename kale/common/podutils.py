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

"""Suite of random helpers regarding pod manipulation."""

import os

from kale.common import k8sutils

NAMESPACE_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"


def is_running_in_pod():
    """Return whether the Kubernetes service-account namespace file exists."""
    return os.path.isfile(NAMESPACE_PATH)


def get_namespace():
    """Get the current namespace."""
    with open(NAMESPACE_PATH) as f:
        return f.read().strip()


def get_pod_name():
    """Get the current pod name."""
    pod_name = os.getenv("HOSTNAME")
    if pod_name is None:
        raise RuntimeError("Env variable HOSTNAME not found.")
    return pod_name


def is_workspace_dir(directory):
    """Check dir path is the container's home folder."""
    return directory == os.getenv("HOME")


def get_pod(name, namespace):
    """Get a pod.

    This function seems redundant but it can save a few repeated lines of code.
    """
    k8s_client = k8sutils.get_v1_client()
    return k8s_client.read_namespaced_pod(name, namespace)
