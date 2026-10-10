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

# Update the version and multi-platform digest from the Kubeflow notebook image
# registry together, then verify the image with make docker-build.
ARG BASE_IMAGE=ghcr.io/kubeflow/kubeflow/notebook-servers/jupyter-scipy:v1.11.0@sha256:8f8a000b7eece82c7e874924dc45a3922e9197137eefe67f55c711cc3ce068fd
FROM ${BASE_IMAGE}

USER root

COPY dist/*.whl /tmp/wheels/
RUN WHEEL=$(ls /tmp/wheels/kubeflow_kale-*.whl) && \
    pip install --no-cache-dir "${WHEEL}[jupyter]" && \
    rm -rf /tmp/wheels

USER 1000
