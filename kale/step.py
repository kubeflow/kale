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
"""Pipeline step data model.

Defines :class:`Step`, the unit of execution inside a Kale :class:`~kale.pipeline.Pipeline`,
together with :class:`StepConfig` and the :class:`PipelineParam` / :class:`Artifact`
named tuples used to describe step inputs and outputs.
"""

from collections.abc import Callable
import logging
from typing import Any, NamedTuple

from kale.common import astutils, runutils
from kale.config import Config, Field, validators
from kale.marshal import Marshaller

log = logging.getLogger(__name__)


class PipelineParam(NamedTuple):
    """A pipeline parameter."""

    param_type: str
    param_value: Any


class Artifact(NamedTuple):
    """A Step artifact."""

    name: str
    type: str
    is_input: bool = False


class StepConfig(Config):
    """Config class used for the Step object."""

    name = Field(type=str, required=True, validators=[validators.StepNameValidator])
    labels = Field(type=dict, default={}, validators=[validators.K8sLabelsValidator])
    annotations = Field(type=dict, default={}, validators=[validators.K8sAnnotationsValidator])
    limits = Field(type=dict, default={}, validators=[validators.K8sLimitsValidator])
    secrets = Field(type=dict, default={}, validators=[validators.K8sSecretsValidator])
    base_image = Field(type=str, default="")
    enable_caching = Field(type=bool)
    generate_html_report = Field(type=bool)
    retry_count = Field(type=int, default=0)
    retry_interval = Field(type=str)
    retry_factor = Field(type=int)
    retry_max_interval = Field(type=str)
    timeout = Field(type=int, validators=[validators.PositiveIntegerValidator])


class Step:
    """Class used to store information about a Step of the pipeline."""

    def __init__(
        self, source: list[str] | Callable, ins: list[Any] = None, outs: list[Any] = None, **kwargs
    ):
        self.source = source
        self.ins = ins or []
        self.outs = outs or []
        self.artifacts: list[Artifact] = []

        self.config = StepConfig(**kwargs)

        # whether the step produces KFP metrics or not
        self.metrics = False
        # the pipeline parameters consumed by the step
        self.parameters: dict[str, PipelineParam] = {}
        self._pps_names = None
        # used to keep track of the "free variables" used by the step
        self.fns_free_variables = {}

    def __call__(self, *args, **kwargs):
        """Handler for when the @step decorated function is called."""
        return execution_handler(self, *args, **kwargs)

    def add_artifact(self, artifact_name, artifact_type, is_input):
        """Helper method to add an artifact to the step.

        Artifact_type will be either 'Dataset', 'Model', 'HTML', 'Metrics',
        'ClassificationMetrics' or 'Artifact'.
        This will simplify tracking what should be an Input[Artifact]
        or Output[Artifact].

        Args:
            artifact_name (str): Name of the artifact.
            artifact_type (str): Type of the artifact.
            is_input (bool): Whether the artifact is an input or output.
        """
        # Check if artifact already exists, update if it's an output
        # TODO: This could be improved to handle more complex cases
        for existing_art in self.artifacts:
            if existing_art.name == artifact_name:
                # If it's an output, ensure its type is set
                if not is_input and existing_art.type is None:
                    existing_art.type = artifact_type
                return

        new_artifact = Artifact(name=artifact_name, type=artifact_type, is_input=is_input)
        self.artifacts.append(new_artifact)

    def run(self, pipeline_parameters_values: dict[str, PipelineParam]):
        """Run the step locally."""
        log.info("%s Running step '%s'... %s", "-" * 10, self.name, "-" * 10)
        # select just the pipeline parameters consumed by this step
        _params = {k: pipeline_parameters_values[k] for k in self.parameters}
        marshaller = Marshaller(
            func=self.source,
            ins=self.ins,
            outs=self.outs,
            parameters=_params,
            marshal_dir=".marshal/",
        )
        marshaller()
        log.info("%s Successfully ran step '%s'... %s", "-" * 10, self.name, "-" * 10)
        runutils.link_artifacts({a.name: a.path for a in self.artifacts})

    @property
    def name(self):
        """Get the name of the step."""
        return self.config.name

    def merge_code(self, source_code: str):
        """Add a new code block to the step.

        Args:
            source_code (str): Python source code to be appended to step
        """
        self.source += [source_code]

    @property
    def pps_names(self):
        """Get the names of the step's parameters sorted."""
        if self._pps_names is None:
            self._pps_names = sorted(self.parameters.keys())
        return self._pps_names

    @property
    def pps_types(self):
        """Get the types of the step's parameters, sorted by name."""
        return [self.parameters[n].param_type for n in self.pps_names]

    @property
    def pps_values(self):
        """Get the values of the step's parameters, sorted by name."""
        return [self.parameters[n].param_value for n in self.pps_names]

    @property
    def rendered_source(self):
        """Source to be rendered in the template."""
        # FIXME: I don't like this approach. Currently step.source is either
        #  a list of strings (if processed from the notebook) or a callable
        #  object (function) (if processed from the sdk). This means that when
        #  rendering the sdk template, we need to get the function's source.
        #  It would be great to, in some way, unify how we treat the "source"
        #  both for the notebook of the SDK all the way from the step object
        #  to the template.
        return astutils.get_function_source(self.source, strip_signature=False)

    @property
    def kfp_inputs(self) -> list[PipelineParam | Artifact]:
        """Get the inputs of the step for KFP.

        This combines PipelineParams and Artifacts marked as inputs.
        Add PipelineParams first (as they're usually positional/keyword args)
        """
        inputs = []

        # Sort them for consistent signature generation
        sorted_param_names = sorted(self.parameters.keys())
        for name in sorted_param_names:
            inputs.append(self.parameters[name])

        # Add Artifacts that are inputs
        for art in sorted(self.artifacts, key=lambda a: a.name):
            if getattr(art, "_is_input", False):  # Check custom input flag
                inputs.append(art)
        return inputs

    @property
    def kfp_outputs(self) -> list[Artifact]:
        """Get Artifacts that are outputs."""
        outputs = []
        for art in sorted(self.artifacts, key=lambda a: a.name):
            if not getattr(art, "_is_input", False):  # Check custom input flag
                outputs.append(art)
        return outputs


class SubPipeline(Step):
    """A referenced notebook, compiled as a nested pipeline.

    A node of the same graph as :class:`Step`, carrying the same ``name``,
    ``ins``, ``outs`` and ``config``, so dependency detection and code
    generation treat a notebook reference and a plain step uniformly.

    ``source`` is the referenced notebook's step code: the boundary scanner
    reads it exactly as it reads a step's, which is what lets a variable cross
    a notebook boundary the same way it crosses a step boundary. ``pipeline``
    is the processed child :class:`~kale.pipeline.Pipeline` that becomes the
    nested sub-DAG.
    """

    def __init__(
        self,
        pipeline,
        notebook_path: str,
        source: list[str] = None,
        ins: list[Any] = None,
        outs: list[Any] = None,
        display_name: str = None,
        imports_and_functions: str = "",
        **kwargs,
    ):
        super().__init__(source=source or [], ins=ins, outs=outs, **kwargs)
        self.pipeline = pipeline
        self.notebook_path = notebook_path
        self._display_name = display_name
        # the referenced notebook's own imports and functions, which its steps
        # are generated with
        self.imports_and_functions = imports_and_functions
        # boundary variable -> name of the inner step that provides it
        self.produced_by: dict[str, str] = {}

    @property
    def display_name(self):
        """Name shown for the nested pipeline, defaulting to a KFP-safe name."""
        return self._display_name or self.name.replace("_", "-")

    def merge_code(self, source_code: str):
        """A notebook reference never absorbs the code of another cell."""
        raise RuntimeError(
            f"Cannot merge code into '{self.name}': it references a notebook rather "
            f"than holding code. Move the code to its own `step:` cell."
        )

    def run(self, pipeline_parameters_values: dict[str, PipelineParam]):
        """Run the referenced notebook's steps locally, in order."""
        for step in self.pipeline.steps:
            step.run(pipeline_parameters_values)


def __default_execution_handler(step: Step, *args, **kwargs):
    log.info("No Pipeline registration handler is set.")
    if not callable(step.source):
        raise RuntimeError(
            "Kale is trying to execute a Step that does not"
            " define a function. Probably this Step was"
            " created converting a Notebook. Kale does not yet"
            " support executing Notebooks locally."
        )
    log.info(f"Executing plain function: '{step.source.__name__}'")
    return step.source(*args, **kwargs)


execution_handler: Callable = __default_execution_handler
