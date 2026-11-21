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
"""Pipeline data model.

Defines :class:`Pipeline` — a :class:`networkx.DiGraph` of :class:`~kale.step.Step`
nodes — along with the configuration classes that describe pipeline-level
settings such as the pipeline name, KFP host, volumes, and Katib experiments.
"""

from collections.abc import Iterable
import copy
import logging

import networkx as nx

from kale.common import graphutils, podutils, utils
from kale.config import Config, Field, validators
from kale.step import PipelineParam, Step

log = logging.getLogger(__name__)


VOLUME_ACCESS_MODE_MAP = {
    "rom": ["ReadOnlyMany"],
    "rwo": ["ReadWriteOnce"],
    "rwm": ["ReadWriteMany"],
}
DEFAULT_VOLUME_ACCESS_MODE = VOLUME_ACCESS_MODE_MAP["rwm"]
DEFAULT_BASE_IMAGE = "python:3.12"


class VolumeConfig(Config):
    """Used for validating the `volumes` field of NotebookConfig."""

    name = Field(type=str, required=True, validators=[validators.K8sNameValidator])
    mount_point = Field(type=str, required=True)
    # Accepted for forward compatibility — snapshot support is not yet implemented
    # in the KFP v2 path. Fields are parsed and stored but have no effect on compilation.
    snapshot = Field(type=bool, default=False)
    snapshot_name = Field(type=str)
    size = Field(type=int)  # fixme: validation for this field?
    size_type = Field(type=str)  # fixme: validation for this field?
    type = Field(type=str, required=True, validators=[validators.VolumeTypeValidator])
    annotations = Field(type=list, default=[])
    storage_class_name = Field(type=str, validators=[validators.K8sNameValidator])
    volume_access_mode = Field(
        type=str, validators=[validators.IsLowerValidator, validators.VolumeAccessModeValidator]
    )
    # When True the compiler injects a KALE_VOLUME_<NAME> env var into every
    # pipeline step alongside the mount_pvc call, making the mount path
    # discoverable at runtime without hard-coding it.
    expose_as_env_var = Field(type=bool, default=False)

    def _parse_annotations(self):
        # Convert annotations to a {k: v} dictionary
        try:
            # TODO: Make JupyterLab annotate with {k: v} instead of
            #  {'key': k, 'value': v}
            self.annotations = {
                a["key"]: a["value"]
                for a in self.annotations
                if a["key"] != "" and a["value"] != ""
            }
        except KeyError as e:
            if str(e) in ["'key'", "'value'"]:
                raise ValueError(
                    "Volume spec: volume annotations must be a list of {'key': k, 'value': v} dicts"
                )
            else:
                raise e

    def _parse_access_mode(self):
        if self.volume_access_mode:
            self.volume_access_mode = VOLUME_ACCESS_MODE_MAP[self.volume_access_mode]

    def _postprocess(self):
        self._parse_annotations()
        self._parse_access_mode()


class KatibConfig(Config):
    """Used to validate the `katib_metadata` field of NotebookConfig."""

    # fixme: improve validation of single fields
    parameters = Field(type=list, default=[])
    objective = Field(type=dict, default={})
    algorithm = Field(type=dict, default={})
    # fixme: Change these names to be Pythonic (need to change how the
    #  labextension passes them)
    maxTrialCount = Field(type=int, default=12)
    maxFailedTrialCount = Field(type=int, default=3)
    parallelTrialCount = Field(type=int, default=3)


class SecurityContextConfig(Config):
    """Configuration for Kubernetes security context settings.

    These settings control the security context applied to all pipeline steps.
    Can be configured via JupyterLab settings or ``KALE_*`` environment variables.
    """

    enabled = Field(type=bool, default=True)
    run_as_user = Field(type=int, default=65534)
    run_as_group = Field(type=int, default=0)
    run_as_non_root = Field(type=bool, default=True)

    def __eq__(self, value):
        if not isinstance(value, SecurityContextConfig):
            return False
        return (
            self.enabled == value.enabled
            and self.run_as_user == value.run_as_user
            and self.run_as_group == value.run_as_group
            and self.run_as_non_root == value.run_as_non_root
        )


class PipelineConfig(Config):
    """Main config class to validate the pipeline metadata."""

    pipeline_name = Field(type=str, required=True, validators=[validators.PipelineNameValidator])
    experiment_name = Field(type=str, required=True)
    pipeline_description = Field(type=str, default="")
    base_image = Field(type=str, default="")
    enable_caching = Field(type=bool, default=True)
    volumes = Field(type=list, items_config_type=VolumeConfig, default=[])
    katib_run = Field(type=bool, default=False)
    katib_metadata = Field(type=KatibConfig)
    abs_working_dir = Field(type=str, default="")
    marshal_path = Field(type=str, default="/tmp/marshal")
    steps_defaults = Field(type=dict, default={})
    kfp_host = Field(type=str)
    storage_class_name = Field(type=str, validators=[validators.K8sNameValidator])
    volume_access_mode = Field(
        type=str, validators=[validators.IsLowerValidator, validators.VolumeAccessModeValidator]
    )
    timeout = Field(type=int, validators=[validators.PositiveIntegerValidator])
    security_context = Field(type=SecurityContextConfig, default=None)
    output_path = Field(type=str, default="", validators=[validators.OutputPathValidator])

    @property
    def source_path(self):
        """Get the path to the main entry point script."""
        return utils.get_main_source_path()

    def _postprocess(self):
        # self._randomize_pipeline_name()
        self._set_base_image()
        self._set_volume_storage_class()
        self._set_volume_access_mode()
        self._sort_volumes()
        self._set_abs_working_dir()
        self._set_security_context()

    def _randomize_pipeline_name(self):
        self.pipeline_name = f"{self.pipeline_name}-{utils.random_string()}"

    def _set_base_image(self):
        if not self.base_image:
            self.base_image = utils.get_default_base_image_from_env() or DEFAULT_BASE_IMAGE

    def _set_volume_storage_class(self):
        if not self.storage_class_name:
            return
        for v in self.volumes:
            if not v.storage_class_name:
                v.storage_class_name = self.storage_class_name

    def _set_volume_access_mode(self):
        if not self.volume_access_mode:
            self.volume_access_mode = DEFAULT_VOLUME_ACCESS_MODE
        else:
            self.volume_access_mode = VOLUME_ACCESS_MODE_MAP[self.volume_access_mode]
        for v in self.volumes:
            if not v.volume_access_mode:
                v.volume_access_mode = self.volume_access_mode

    def _sort_volumes(self):
        # The Jupyter Web App assumes the first volume of the notebook is the
        # working directory, so we make sure to make it appear first in the
        # spec.
        self.volumes = sorted(
            self.volumes, reverse=True, key=lambda _v: podutils.is_workspace_dir(_v.mount_point)
        )

    def _set_abs_working_dir(self):
        if not self.abs_working_dir:
            self.abs_working_dir = utils.abs_working_dir(self.source_path)

    def _set_security_context(self):
        """Initialize security context from env vars if not set from metadata.

        Precedence: JupyterLab metadata > env vars > defaults
        """
        env_config = utils.get_security_context_from_env()
        if self.security_context is None:
            self.security_context = env_config


class Pipeline(nx.DiGraph):
    """A Pipeline that can be converted into a KFP pipeline.

    This class is used to define a pipeline, its steps and all its
    configurations. It extends nx.DiGraph to exploit some graph-related
    algorithms but provides helper functions to work with Step objects
    instead of standard networkx "nodes". This makes it simpler to access
    the steps of the pipeline and their attributes.
    """

    def __init__(self, config: PipelineConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.pipeline_parameters: dict[str, PipelineParam] = {}
        self.processor = None
        self._pps_names = None

    def run(self):
        """Runs the steps locally in topological sort."""
        for step in self.steps:
            step.run(self.pipeline_parameters)

    def add_step(self, step: Step):
        """Add a new Step to the pipeline."""
        if not isinstance(step, Step):
            raise RuntimeError("Not of type Step.")
        if step.name in self.steps_names:
            raise RuntimeError(f"Step with name '{step.name}' already exists")
        self.add_node(step.name, step=step)

    def add_dependency(self, parent: Step, child: Step):
        """Link two Steps in the pipeline."""
        self.add_edge(parent.name, child.name)

    def get_step(self, name: str) -> Step:
        """Get the Step with the provided name."""
        return self.nodes()[name]["step"]

    @property
    def steps(self) -> Iterable[Step]:
        """Get the Steps objects sorted topologically."""
        return (self.nodes()[x]["step"] for x in self.steps_names)

    @property
    def steps_names(self):
        """Get all Steps' names, sorted topologically."""
        return [step.name for step in self._topological_sort()]

    @property
    def all_steps_parameters(self):
        """Create a dict with step names and their parameters."""
        return {step: sorted(self.get_step(step).parameters.keys()) for step in self.steps_names}

    @property
    def pipeline_dependencies_tasks(self):
        """Generate a dictionary of Pipeline dependencies."""
        return {step_name: list(self.predecessors(step_name)) for step_name in self.steps_names}

    @property
    def pps_names(self):
        """Get the names of the pipeline parameters sorted."""
        if self._pps_names is None:
            self._pps_names = sorted(self.pipeline_parameters.keys())
        return self._pps_names

    @property
    def pps_types(self):
        """Get the types of the pipeline parameters, sorted by name."""
        return [self.pipeline_parameters[n].param_type for n in self.pps_names]

    @property
    def pps_values(self):
        """Get the values of the pipeline parameters, sorted by name."""
        return [self.pipeline_parameters[n].param_value for n in self.pps_names]

    def _topological_sort(self) -> Iterable[Step]:
        return self._steps_iterable(nx.topological_sort(self))

    def get_ordered_ancestors(self, step_name: str) -> Iterable[Step]:
        """Return the ancestors of a step in an ordered manner.

        Wrapper of graphutils.get_ordered_ancestors.

        Returns:
            Iterable[Step]: A Steps iterable.
        """
        return self._steps_iterable(graphutils.get_ordered_ancestors(self, step_name))

    def _steps_iterable(self, step_names: Iterable[str]) -> Iterable[Step]:
        for name in step_names:
            yield self.get_step(name)

    def get_leaf_steps(self):
        """Get the list of leaf steps of the pipeline.

        A step is considered a leaf when its in-degree is > 0 and its
        out-degree is 0.

        Returns (list): A list of leaf Steps.
        """
        return [x for x in self.steps if self.out_degree(x.name) == 0]

    def override_pipeline_parameters_from_kwargs(self, **kwargs):
        """Overwrite the current pipeline parameters with provided inputs."""
        _pipeline_parameters = copy.deepcopy(self.pipeline_parameters)
        for k, v in kwargs.items():
            if k not in self.pipeline_parameters:
                raise RuntimeError(
                    f"Running pipeline '{self.config.pipeline_name}' with"
                    " an input argument that is not in its"
                    f" parameters: {k}"
                )
            # replace default value with the provided one
            _type = _pipeline_parameters[k].param_type
            _pipeline_parameters[k] = PipelineParam(_type, v)
        self.pipeline_parameters = _pipeline_parameters

    def show(self):
        """Print the pipeline nodes and dependencies in a table."""
        from tabulate import tabulate

        data = []
        for step in self.steps:
            data.append([step.name, list(self.predecessors(step.name))])
        log.info("Pipeline layout:")
        log.info("\n" + tabulate(data, headers=["Step", "Depends On"]) + "\n")
