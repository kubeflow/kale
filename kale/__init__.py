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

__version__ = "2.3.0"

from typing import Any, NamedTuple


class PipelineParam(NamedTuple):
    """A pipeline parameter."""

    param_type: str
    param_value: Any


class Artifact(NamedTuple):
    """A Step artifact."""

    name: str
    type: str
    is_input: bool = False


from kale.common import logutils

from .compiler import Compiler
from .pipeline import Pipeline, PipelineConfig, VolumeConfig
from .processors import NotebookConfig, NotebookProcessor
from .step import Step, StepConfig

__all__ = [
    "PipelineParam",
    "Artifact",
    "NotebookConfig",
    "NotebookProcessor",
    "Step",
    "StepConfig",
    "Pipeline",
    "PipelineConfig",
    "VolumeConfig",
    "Compiler",
    "marshal",
]

logutils.get_or_create_logger(module=__name__, name="kale")
del logutils
