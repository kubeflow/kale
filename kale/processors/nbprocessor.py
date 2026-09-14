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
"""Notebook → Pipeline conversion.

:class:`NotebookProcessor` reads a Jupyter notebook, parses the Kale-specific
cell tags and notebook metadata, resolves static data dependencies, and
produces a ready-to-compile :class:`~kale.pipeline.Pipeline`.
"""

import logging
import os
import re
from typing import Any

import nbformat as nb
import networkx as nx

from kale.common import astutils, flakeutils, graphutils, kfutils, utils
from kale.config import Field
from kale.pipeline import Pipeline, PipelineConfig
from kale.step import PipelineParam, Step, SubPipeline

log = logging.getLogger(__name__)

# fixme: Change the name of this key to `kale_metadata`
KALE_NB_METADATA_KEY = "kubeflow_notebook"

SKIP_TAG = r"^skip$"
IMPORT_TAG = r"^imports$"
FUNCTIONS_TAG = r"^functions$"
PREV_TAG = r"^prev:[_a-z]([_a-z0-9]*)?$"
STEP_TAG = r"^step:([_a-z]([_a-z0-9]*)?)?$"
# A `notebook:<name>` cell references another notebook as a sub-pipeline. The
# referenced path is carried in the cell metadata (`notebook_path`), not the tag.
NOTEBOOK_TAG = r"^notebook:([_a-z]([_a-z0-9]*)?)?$"
PIPELINE_PARAMETERS_TAG = r"^pipeline-parameters$"
PIPELINE_METRICS_TAG = r"^pipeline-metrics$"
# Annotations map to actual pod annotations that can be set via KFP SDK
_segment = "[a-zA-Z0-9]+([a-zA-Z0-9-_.]*[a-zA-Z0-9])?"
K8S_ANNOTATION_KEY = f"{_segment}([/]{_segment})?"
ANNOTATION_TAG = rf"^annotation:{K8S_ANNOTATION_KEY}:(.*)$"
LABEL_TAG = rf"^label:{K8S_ANNOTATION_KEY}:(.*)$"
# Limits map to K8s limits, like CPU, Mem, GPU, ...
# E.g.: limit:nvidia.com/gpu:2
LIMITS_TAG = r"^limit:([_a-z-\.\/]+):([_a-zA-Z0-9\.]+)$"
# Image tag for per-step Base image selection
# E.g.: image:python:3.11-slim
IMAGE_TAG = r"^image:(.+)$"
# Cache tag for per-step caching control
# E.g.: cache:enabled or cache:disabled
CACHE_ENABLED = "enabled"
CACHE_DISABLED = "disabled"
CACHE_TAG = rf"^cache:({CACHE_ENABLED}|{CACHE_DISABLED})$"
# Report tag for per-step HTML report generation control
# E.g.: report:enabled or report:disabled
REPORT_ENABLED = "enabled"
REPORT_DISABLED = "disabled"
REPORT_TAG = rf"^report:({REPORT_ENABLED}|{REPORT_DISABLED})$"

_TAGS_LANGUAGE = [
    SKIP_TAG,
    IMPORT_TAG,
    FUNCTIONS_TAG,
    PREV_TAG,
    STEP_TAG,
    NOTEBOOK_TAG,
    PIPELINE_PARAMETERS_TAG,
    PIPELINE_METRICS_TAG,
    ANNOTATION_TAG,
    LABEL_TAG,
    LIMITS_TAG,
    IMAGE_TAG,
    CACHE_TAG,
    REPORT_TAG,
]
# These tags are applied to every step of the pipeline
_STEPS_DEFAULTS_LANGUAGE = [ANNOTATION_TAG, LABEL_TAG, LIMITS_TAG, IMAGE_TAG, CACHE_TAG, REPORT_TAG]


METRICS_TEMPLATE = """\
from kale.common import kfputils as _kale_kfputils
_kale_kfp_metrics = {
%s
}
_kale_kfputils.generate_mlpipeline_metrics(_kale_kfp_metrics)\
"""

KFP_ARTIFACT_TYPE_MAP = {
    "model": "Model",  # if "model" in var_name.lower()-> kfp.dsl.Model
    "dataset": "Dataset",  # if "dataset" in var_name.lower()-> kfp.dsl.Dataset
    "data": "Dataset",  # if "data" in var_name.lower()-> kfp.dsl.Dataset
    "metrics": "Metrics",  # if "metrics" in var_name.lower()-> kfp.dsl.Metrics
    "classification": "ClassificationMetrics",
    r"a-zA-Z0-9_": "Artifact",  # default for any other variable
}


def get_annotation_or_label_from_tag(tag_parts):
    """Get the key and value from an annotation or label tag.

    Args:
        tag_parts: annotation or label notebook tag

    Returns (tuple): key (annotation or label name), values
    """
    # Since value can be anything, merge together everything that's left.
    return tag_parts[0], "".join(tag_parts[1:])


def get_limit_from_tag(tag_parts):
    """Get the key and value from a notebook limit tag.

    Args:
        tag_parts: annotation or label notebook tag

    Returns (tuple): key (limit name), values
    """
    return tag_parts.pop(0), tag_parts.pop(0)


class NotebookConfig(PipelineConfig):
    """Config store for a notebook.

    This config extends the base pipeline config to take into account some
    small differences in the handling of a notebook.
    """

    notebook_path = Field(type=str, required=True)
    # FIXME: Probably this can be removed. The labextension passes both
    #  'experiment_name' and 'experiment', but the latter is not used in the
    #  backend.
    experiment = Field(type=dict)

    # Accepted for forward compatibility — snapshot support is not yet
    # implemented in the KFP v2 path. The field is parsed and stored but
    # has no effect on compilation. Will be wired up in a future iteration.
    snapshot_volumes = Field(type=bool, default=False)

    @property
    def source_path(self):
        """Get the path to the source notebook."""
        return self.notebook_path

    def _preprocess(self, kwargs):
        kwargs["steps_defaults"] = self._parse_steps_defaults(kwargs.get("steps_defaults"))

    def _parse_steps_defaults(self, steps_defaults):
        """Parse common step configuration defined in the metadata."""
        result = {}

        if not isinstance(steps_defaults, list):
            return steps_defaults

        for c in steps_defaults:
            if any(re.match(_c, c) for _c in _STEPS_DEFAULTS_LANGUAGE) is False:
                raise ValueError(f"Unrecognized common step configuration: {c}")

            parts = c.split(":")

            conf_type = parts.pop(0)
            if conf_type in ["annotation", "label"]:
                result_key = f"{conf_type}s"
                if result_key not in result:
                    result[result_key] = {}
                key, value = get_annotation_or_label_from_tag(parts)
                result[result_key][key] = value

            if conf_type == "limit":
                if "limits" not in result:
                    result["limits"] = {}
                key, value = get_limit_from_tag(parts)
                result["limits"][key] = value

            if conf_type == "image":
                # Image tag value is the rest after 'image:'
                result["base_image"] = ":".join(parts)

            if conf_type == "cache":
                # Cache value is 'enabled' or 'disabled'
                cache_value = parts.pop(0)
                result["enable_caching"] = cache_value == CACHE_ENABLED

            if conf_type == "report":
                # Report value is 'enabled' or 'disabled'
                report_value = parts.pop(0)
                result["generate_html_report"] = report_value == REPORT_ENABLED
        return result


class NotebookProcessor:
    """Convert a Notebook to a Pipeline object."""

    no_op_step = Step(name="no_op", source=[])

    def __init__(
        self,
        nb_path: str,
        nb_metadata_overrides: dict[str, Any] | None = None,
        config: NotebookConfig | None = None,
        skip_validation: bool = False,
        _referencing: tuple[str, ...] = (),
        **kwargs,
    ):
        """Instantiate a new NotebookProcessor.

        Args:
            nb_path: Path to source notebook
            nb_metadata_overrides: Override notebook config settings
            config: Optional pre-built NotebookConfig
            skip_validation: Set to True in order to skip the notebook's
                metadata validation. This is useful in case the
                NotebookProcessor is used to parse a part of the notebook
                (e.g., retrieve pipeline metrics) and the notebook config (for
                pipeline generation) might still be invalid.
            _referencing: Notebooks already being processed up the reference
                chain, used to detect a cycle. Set when a processor spawns a
                child for a ``notebook:`` cell.
        """
        self.skip_validation = skip_validation
        # number of leading `source` entries every step shares (imports and
        # functions), set once the notebook is parsed
        self._shared_block_count = 0
        self.nb_path = os.path.expanduser(nb_path)
        self._referencing = _referencing + (os.path.abspath(self.nb_path),)
        self.notebook = self._read_notebook()

        nb_metadata = self.notebook.metadata.get(KALE_NB_METADATA_KEY, {})
        nb_metadata.update({"notebook_path": nb_path})
        if nb_metadata_overrides:
            nb_metadata.update(nb_metadata_overrides)

        # Initialize config and pipeline (previously in BaseProcessor)
        self.config = config
        if not config and not skip_validation:
            self.config = NotebookConfig(**{**kwargs, **nb_metadata})
        self.pipeline = Pipeline(self.config) if self.config else None

    def _read_notebook(self):
        if not os.path.exists(self.nb_path):
            raise ValueError(f"NotebookProcessor could not find a notebook at path {self.nb_path}")
        return nb.read(self.nb_path, as_version=nb.NO_CONVERT)

    def run(self) -> Pipeline:
        """Process the notebook into a Pipeline object."""
        self.to_pipeline()
        self._post_pipeline()
        return self.pipeline

    def _post_pipeline(self):
        """Post-process the pipeline after conversion."""
        if self.pipeline:
            self.pipeline.processor = self
        self._configure_poddefaults()
        self._apply_steps_defaults()

    def _configure_poddefaults(self):
        """Detect and configure PodDefaults labels."""
        _pod_defaults_labels = {}
        try:
            _pod_defaults_labels = kfutils.find_poddefault_labels()
        except Exception as e:
            log.warning("Could not retrieve PodDefaults. Reason: %s", e)
        self.pipeline.config.steps_defaults["labels"] = {
            **self.pipeline.config.steps_defaults.get("labels", {}),
            **_pod_defaults_labels,
        }

    def _apply_steps_defaults(self):
        """Apply default configuration to all pipeline steps.

        A composition's defaults are global, so a referenced notebook's own
        steps take them too. A step that sets the same key itself keeps its
        own value.
        """
        for step in self.pipeline.steps:
            step.config.update(self.pipeline.config.steps_defaults)
            if isinstance(step, SubPipeline):
                for inner in step.pipeline.steps:
                    inner.config.update(self.pipeline.config.steps_defaults)

    def to_pipeline(self):
        """Convert an annotated Notebook to a Pipeline object."""
        (pipeline_parameters_source, pipeline_metrics_source, imports_and_functions) = (
            self.parse_notebook()
        )

        self.parse_pipeline_parameters(pipeline_parameters_source)
        # a referenced notebook is processed before this notebook's own
        # parameters are known, so they are handed down here
        self.propagate_pipeline_parameters()
        # get a list of variables that need to be logged as pipeline metrics
        pipeline_metrics = astutils.parse_metrics_print_statements(pipeline_metrics_source)

        # a composition has no `prev:` tags between its units, so its edges are
        # inferred before the graph is resolved
        self.link_composition_units()
        # run static analysis over the source code
        self.dependencies_detection(imports_and_functions)
        self.propagate_subpipeline_boundaries()
        self.assign_metrics(pipeline_metrics)

        # TODO: Additional action required:
        #  Run a static analysis over every step to check that pipeline
        #  parameters are not assigned with new values.

    def parse_pipeline_parameters(self, source: str):
        """Get pipeline parameters from source code."""
        pipeline_parameters = astutils.parse_assignments_expressions(source)
        for name, (v_type, v_value) in pipeline_parameters.items():
            pipeline_parameters[name] = PipelineParam(v_type, v_value)
        self.pipeline.pipeline_parameters = pipeline_parameters

    def parse_notebook(self):
        """Creates a NetworkX graph based on the input notebook's tags.

        Cell's source code are embedded into the graph as node attributes.
        """
        # will be assigned at the end of each for loop
        prev_step_name = None

        # A `notebook:` cell is a reference, not code, so it breaks the merge
        # chain: untagged cells that follow it are held here and attached to
        # the next `step:` cell, never merged backwards into a previous step.
        pending_sources = []
        awaiting_step = False

        # All the code cells that have to be pre-pended to every pipeline step
        # (i.e., imports and functions) are merged here
        imports_block = []
        functions_block = []

        # Variables that will become pipeline parameters
        pipeline_parameters = []
        # Variables that will become pipeline metrics
        pipeline_metrics = []

        # Tags whose cell absorbs the untagged cells that follow it, and the
        # block each one appends to. A `step:` cell absorbs into the step
        # itself, `skip` is transparent, and a `notebook:` reference absorbs
        # nothing (it hands the cells forward instead).
        merge_targets = {
            "imports": imports_block,
            "functions": functions_block,
            "pipeline-parameters": pipeline_parameters,
            "pipeline-metrics": pipeline_metrics,
        }

        for c in self.notebook.cells:
            if c.cell_type != "code":
                continue

            tags = self.parse_cell_metadata(c.metadata)

            if len(tags["step_names"]) > 1:
                raise NotImplementedError(
                    "Kale does not yet support multiple"
                    " step names in a single notebook"
                    " cell. One notebook cell was found"
                    " with {}  step names".format(tags["step_names"])
                )

            # get the step name from the tags
            step_name = tags["step_names"][0] if len(tags["step_names"]) > 0 else None

            if tags["notebook_names"]:
                # a reference cell holds no code of its own, and dropping it
                # silently is how you lose work when a code cell is switched to
                # the Notebook type. Comments are fine, the UI writes one.
                if any(
                    line.strip() and not line.strip().startswith("#")
                    for line in c.source.splitlines()
                ):
                    raise ValueError(
                        f"`notebook:{tags['notebook_names'][0]}` cell contains code."
                        " A cell that references a notebook holds no code of its own."
                        " Move the code to its own `step:` cell."
                    )
                # the reference breaks the merge chain
                if pending_sources:
                    raise ValueError(
                        "Untagged code after a `notebook:` cell must be followed by"
                        " a `step:` cell that owns it (found another `notebook:`"
                        " cell first)."
                    )
                self._add_notebook_reference(tags["notebook_names"][0], tags.get("notebook_path"))
                prev_step_name = None
                awaiting_step = True
                continue

            if step_name == "skip":
                # when the cell is skipped, don't store `skip` as the previous
                # active cell
                continue
            if step_name in merge_targets:
                merge_targets[step_name].append(c.source)
                prev_step_name = step_name
                awaiting_step = False
                continue

            # if none of the above apply, then we are parsing a code cell with
            # a block names and (possibly) some dependencies

            # if the cell was not tagged with a step name,
            # add the code to the previous cell
            if not step_name:
                if awaiting_step:
                    # held for the next `step:` cell
                    pending_sources.append(c.source)
                elif prev_step_name in merge_targets:
                    merge_targets[prev_step_name].append(c.source)
                # prev_step_name might be None in case the first cells of the
                # notebooks have not been tagged.
                elif prev_step_name:
                    # this notebook cell will be merged to a previous one that
                    # specified a step name
                    self.pipeline.get_step(prev_step_name).merge_code(c.source)
            else:
                # in this branch we are sure that we are reading a code cell
                # with a step tag, so we must not allow for pipeline-metrics
                if prev_step_name == "pipeline-metrics":
                    raise ValueError(
                        "Tag pipeline-metrics must be placed on a"
                        " cell at the end of the Notebook."
                        " Pipeline metrics should be considered"
                        " as a result of the pipeline execution"
                        " and not of single steps."
                    )
                # add node to DAG, adding tags and source code of notebook cell,
                # prepending any cells held since the last `notebook:` cell
                if step_name not in self.pipeline.nodes:
                    step = Step(
                        name=step_name,
                        source=pending_sources + [c.source],
                        ins=[],
                        outs=[],
                        limits=tags.get("limits", {}),
                        labels=tags.get("labels", {}),
                        annotations=tags.get("annotations", {}),
                        base_image=tags.get("base_image", ""),
                        enable_caching=tags.get("enable_caching"),
                        generate_html_report=tags.get("generate_html_report"),
                    )
                    self.pipeline.add_step(step)
                    for _prev_step in tags["prev_steps"]:
                        if _prev_step not in self.pipeline.nodes:
                            raise ValueError(
                                "Step {} does not exist. It was "
                                "defined as previous step of {}".format(
                                    _prev_step, tags["step_names"]
                                )
                            )
                        self.pipeline.add_edge(_prev_step, step_name)
                else:
                    for pending in pending_sources:
                        self.pipeline.get_step(step_name).merge_code(pending)
                    self.pipeline.get_step(step_name).merge_code(c.source)

                pending_sources = []
                awaiting_step = False
                prev_step_name = step_name

        if pending_sources:
            raise ValueError(
                "Untagged code after a `notebook:` cell must be followed by a"
                " `step:` cell that owns it (reached the end of the notebook)."
            )

        # Prepend any `imports` and `functions` cells to every Pipeline step
        shared_blocks = imports_block + functions_block
        for step in self.pipeline.steps:
            step.source = shared_blocks + step.source
        # a referencing notebook scans this notebook's steps for boundary
        # variables, and these blocks belong to every step, not to its interface
        self._shared_block_count = len(shared_blocks)

        # merge together pipeline parameters
        pipeline_parameters = "\n".join(pipeline_parameters)
        # merge together pipeline metrics
        pipeline_metrics = "\n".join(pipeline_metrics)

        imports_and_functions = "\n".join(imports_block + functions_block)
        return pipeline_parameters, pipeline_metrics, imports_and_functions

    def link_composition_units(self):
        """Infer the edges between the units of a composition.

        A notebook that references others has no ``prev:`` tags to order its
        units, so the edges are inferred here, before the graph is resolved:

        - data flow: a unit that provides a variable another one is missing
          becomes its ancestor. This is the detection Kale already runs between
          cells, applied one level up.
        - reading order: a ``step:`` cell of this notebook runs after every unit
          above it and before every unit below it, so a notebook that mixes
          steps and references runs the way it reads. Two references with
          nothing between them get no edge, so independent notebooks still run
          in parallel.

        A notebook with no references keeps Kale's explicit ``prev:`` semantics
        and is left untouched.
        """
        spine = [self.pipeline.get_step(name) for name in self.pipeline.nodes()]
        if not any(isinstance(unit, SubPipeline) for unit in spine):
            return

        missing, provided = {}, {}
        for unit in spine:
            code = "\n".join(unit.source)
            missing[unit.name] = set(flakeutils.pyflakes_report(code=code))
            # a variable a unit consumes is not one it provides: the
            # subtraction is what orients the edge
            provided[unit.name] = set(astutils.get_marshal_candidates(code)) - missing[unit.name]

        producers = {}
        for unit in spine:
            for var in provided[unit.name]:
                producers.setdefault(var, []).append(unit.name)

        for unit in spine:
            for var in sorted(missing[unit.name]):
                sources = [s for s in producers.get(var, []) if s != unit.name]
                if not sources:
                    continue
                if len(sources) > 1:
                    raise ValueError(
                        f"'{unit.name}' consumes '{var}', but it is defined in multiple "
                        f"notebooks/steps ({', '.join(sorted(sources))}). Rename it so a "
                        f"single one produces the value."
                    )
                self.pipeline.add_edge(sources[0], unit.name)

        for i, unit in enumerate(spine):
            for other in spine[i + 1 :]:
                if isinstance(unit, SubPipeline) and isinstance(other, SubPipeline):
                    continue
                self.pipeline.add_edge(unit.name, other.name)

        if not nx.is_directed_acyclic_graph(self.pipeline):
            raise ValueError(
                "Cycle detected in the composition graph. Each cell must appear below "
                "the cells that produce the variables it uses."
            )

    def propagate_pipeline_parameters(self):
        """Hand this notebook's pipeline parameters to the notebooks it references.

        A composition exposes one set of parameters, the root's, so a step in a
        referenced notebook that uses one has to receive it like any other step
        does. Where both notebooks declare the same name the root's value wins,
        since that is the one a run is submitted with; the referenced
        notebook's own value stays its default when it is compiled on its own.
        """
        if not self.pipeline.pipeline_parameters:
            return
        for node in self.pipeline.steps:
            if isinstance(node, SubPipeline):
                node.pipeline.pipeline_parameters = {
                    **node.pipeline.pipeline_parameters,
                    **self.pipeline.pipeline_parameters,
                }

    def propagate_subpipeline_boundaries(self):
        """Push a referenced notebook's boundary variables onto its own steps.

        Resolution marks the variables that cross into and out of a
        :class:`~kale.step.SubPipeline`, but the artifacts are produced and
        consumed by the steps inside it. This hands each variable to the step
        that actually provides or needs it, so the component generator exposes
        it exactly as it does for a variable crossing two cells.
        """
        for unit in self.pipeline.steps:
            if not isinstance(unit, SubPipeline):
                continue
            inner = list(unit.pipeline.steps)
            for var in unit.outs:
                provider = None
                for step in inner:
                    code = "\n".join(step.source)
                    missing = set(flakeutils.pyflakes_report(code=code))
                    if var in set(astutils.get_marshal_candidates(code)) - missing:
                        provider = step
                if provider is None:
                    raise ValueError(
                        f"'{unit.name}' is expected to produce '{var}', but none of its "
                        f"steps provides it. This is a bug in Kale's boundary detection."
                    )
                if var not in provider.outs:
                    provider.outs.append(var)
                unit.produced_by[var] = provider.name
            for var in unit.ins:
                consumers = [
                    step
                    for step in inner
                    if var in flakeutils.pyflakes_report(code="\n".join(step.source))
                ]
                if not consumers:
                    raise ValueError(
                        f"'{unit.name}' is expected to consume '{var}', but none of its "
                        f"steps requires it. This is a bug in Kale's boundary detection."
                    )
                for step in consumers:
                    if var not in step.ins:
                        step.ins.append(var)

    def _add_notebook_reference(self, name: str, rel_path: str):
        """Process a referenced notebook and attach it as a graph node.

        The reference is compiled by a processor of its own, so a notebook is
        parsed the same way whether it is compiled directly or composed. The
        resulting :class:`~kale.step.SubPipeline` sits in the graph next to the
        steps of this notebook, and its source is the referenced notebook's step
        code, which is what dependency detection reads to resolve variables
        across the boundary.
        """
        if not rel_path:
            raise ValueError(
                f"`notebook:{name}` cell is missing a 'notebook_path' in its cell metadata."
            )
        if len(self._referencing) > 1:
            raise ValueError(
                f"`notebook:{name}` is nested inside "
                f"'{os.path.basename(self.nb_path)}', which is itself referenced by "
                f"another notebook. Nested references are not supported yet: reference "
                f"every notebook from the root notebook instead."
            )
        path = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(self.nb_path)), rel_path)
        )
        if os.path.abspath(path) in self._referencing:
            chain = " -> ".join(os.path.basename(p) for p in self._referencing)
            raise ValueError(
                f"`notebook:{name}` creates a reference cycle ({chain} -> "
                f"{os.path.basename(path)}). A notebook cannot reference itself, "
                f"directly or through another notebook."
            )

        processor = NotebookProcessor(
            path,
            {
                "pipeline_name": name.replace("_", "-"),
                "experiment_name": self.pipeline.config.experiment_name,
            },
            _referencing=self._referencing,
        )
        pipeline = processor.run()
        self.pipeline.add_step(
            SubPipeline(
                pipeline=pipeline,
                notebook_path=path,
                # only what runs as a step, minus the blocks every step
                # shares: neither untagged cells nor imports are values this
                # notebook offers across the boundary
                source=[
                    "\n".join(
                        "\n".join(s.source[processor._shared_block_count :]) for s in pipeline.steps
                    )
                ],
                imports_and_functions=processor.get_imports_and_functions(),
                name=name,
                base_image=pipeline.config.base_image,
            )
        )

    def parse_cell_metadata(self, metadata):
        """Parse a notebook's cell's metadata field.

        The Kale UI writes specific tags inside the 'tags' field, as a list
        of string tags. Supported tags are defined by _TAGS_LANGUAGE.

        Args:
            metadata (dict): a dict containing a notebook's cell's metadata

        Returns (dict): parsed tags based on Kale tagging language

        """
        parsed_tags = {}

        # `step_names` is a list because a notebook cell might be assigned to
        # more than one Pipeline step.
        parsed_tags["step_names"] = []
        parsed_tags["prev_steps"] = []
        # names of notebooks referenced by `notebook:` cells (sub-pipelines)
        parsed_tags["notebook_names"] = []
        # define intermediate variables so that dicts are not added to a steps
        # when they are empty
        cell_annotations = {}
        cell_labels = {}
        cell_limits = {}
        cell_base_image = None
        cell_enable_caching = None
        cell_generate_html_report = None

        # the notebook cell was not tagged
        if "tags" not in metadata or len(metadata["tags"]) == 0:
            return parsed_tags

        for t in metadata["tags"]:
            if not isinstance(t, str):
                raise ValueError(f"Tags must be string. Found tag {t} of type {type(t)}")
            # Check that the tag is defined by the Kale tagging language
            if any(re.match(_t, t) for _t in _TAGS_LANGUAGE) is False:
                raise ValueError(f"Unrecognized tag: {t}")

            # Special tags have a specific effect on the cell they belong to.
            # Specifically:
            #  - skip: ignore the notebook cell
            #  - pipeline-parameters: use the cell to populate Pipeline
            #       parameters. The cell must contain only assignment
            #       expressions
            #  - pipeline-metrics: use the cell to populate Pipeline metrics.
            #       The cell must contain only variable names
            #  - imports: the code of the corresponding cell(s) will be
            #       prepended to every Pipeline step
            #  - functions: same as imports, but the corresponding code is
            #       placed **after** `imports`
            special_tags = [
                "skip",
                "pipeline-parameters",
                "pipeline-metrics",
                "imports",
                "functions",
            ]
            if t in special_tags:
                parsed_tags["step_names"] = [t]
                return parsed_tags

            # now only `step` and `prev` tags remain to be parsed.
            tag_parts = t.split(":")
            tag_name = tag_parts.pop(0)

            if tag_name == "annotation":
                key, value = get_annotation_or_label_from_tag(tag_parts)
                cell_annotations.update({key: value})

            if tag_name == "label":
                key, value = get_annotation_or_label_from_tag(tag_parts)
                cell_labels.update({key: value})

            if tag_name == "limit":
                key, value = get_limit_from_tag(tag_parts)
                cell_limits.update({key: value})

            if tag_name == "image":
                # Image value is the rest after 'image:'
                cell_base_image = ":".join(tag_parts)

            if tag_name == "cache":
                # Cache value is 'enabled' or 'disabled'
                cache_value = tag_parts.pop(0)
                cell_enable_caching = cache_value == CACHE_ENABLED

            if tag_name == "report":
                # Report value is 'enabled' or 'disabled'
                report_value = tag_parts.pop(0)
                cell_generate_html_report = report_value == REPORT_ENABLED

            # name of the referenced notebook, compiled as a sub-pipeline. Its
            # path comes from the cell metadata, not from the tag.
            if tag_name == "notebook":
                parsed_tags["notebook_names"].append(tag_parts.pop(0))
                parsed_tags["notebook_path"] = metadata.get("notebook_path")

            # name of the future Pipeline step
            if tag_name in ["step"]:
                step_name = tag_parts.pop(0)
                parsed_tags["step_names"].append(step_name)
            # name(s) of the father Pipeline step(s)
            if tag_name == "prev":
                prev_step_name = tag_parts.pop(0)
                parsed_tags["prev_steps"].append(prev_step_name)

        if not parsed_tags["step_names"] and parsed_tags["prev_steps"]:
            raise ValueError(
                "A cell can not provide `prev` annotations without "
                "providing a `step` annotation as well"
            )
        missing_step_names = not parsed_tags["step_names"]
        if cell_annotations:
            if missing_step_names:
                raise ValueError(
                    "A cell can not provide Pod annotations in a cell"
                    " that does not declare a step name."
                )
            parsed_tags["annotations"] = cell_annotations

        if cell_labels:
            if missing_step_names:
                raise ValueError(
                    "A cell can not provide Pod labels in a cell that does not declare a step name."
                )
            parsed_tags["labels"] = cell_labels

        if cell_limits:
            if missing_step_names:
                raise ValueError(
                    "A cell can not provide Pod resource limits in a"
                    " cell that does not declare a step name."
                )
            parsed_tags["limits"] = cell_limits

        if cell_base_image:
            if missing_step_names:
                raise ValueError(
                    "A cell can not provide a base image in a"
                    " cell that does not declare a step name."
                )
            parsed_tags["base_image"] = cell_base_image

        if cell_enable_caching is not None:
            if missing_step_names:
                raise ValueError(
                    "A cell can not provide caching control in a"
                    " cell that does not declare a step name."
                )
            parsed_tags["enable_caching"] = cell_enable_caching

        if cell_generate_html_report is not None:
            if missing_step_names:
                raise ValueError(
                    "A cell can not provide HTML report control in a"
                    " cell that does not declare a step name."
                )
            parsed_tags["generate_html_report"] = cell_generate_html_report
        return parsed_tags

    def get_pipeline_parameters_source(self):
        """Get just pipeline parameters cells from the notebook.

        Returns (str): pipeline parameters source code
        """
        return self._get_reserved_tag_source(PIPELINE_PARAMETERS_TAG)

    def get_pipeline_metrics_source(self):
        """Get just pipeline metrics cells from the notebook.

        Returns (str): pipeline metrics source code
        """
        # check that the pipeline metrics tag is only assigned to cells at
        # the end of the notebook
        detected = False
        tags = _TAGS_LANGUAGE[:]
        tags.remove(PIPELINE_METRICS_TAG)

        for c in self.notebook.cells:
            # parse only source code cells
            if c.cell_type != "code":
                continue

            # if we see a pipeline-metrics tag, set the flag
            if (
                "tags" in c.metadata
                and len(c.metadata["tags"]) > 0
                and any(re.match(PIPELINE_METRICS_TAG, t) for t in c.metadata["tags"])
            ):
                detected = True
                continue

            # if we have the flag set and we detect any other tag from the tags
            # language, then raise error
            if (
                detected
                and "tags" in c.metadata
                and len(c.metadata["tags"]) > 0
                and any(any(re.match(tag, t) for t in c.metadata["tags"]) for tag in tags)
            ):
                raise ValueError(
                    "Tag pipeline-metrics tag must be placed on a "
                    "cell at the end of the Notebook."
                    " Pipeline metrics should be considered as a"
                    " result of the pipeline execution and not of"
                    " single steps."
                )
        return self._get_reserved_tag_source(PIPELINE_METRICS_TAG)

    def get_imports_and_functions(self):
        """Get the global code that runs at the beginning of every step."""
        return "\n".join(
            [
                self._get_reserved_tag_source(IMPORT_TAG),
                self._get_reserved_tag_source(FUNCTIONS_TAG),
            ]
        )

    def _get_reserved_tag_source(self, search_tag):
        """Get just the specific tag's source code.

        When searching for tag x, will return all cells that are tagged with x
        and, if untagged, follow cells with tag x. The result is a multiline
        string containing all the python code associated to x.

        Note: This is designed for 'special' tags, as the STEP_TAG is excluded
              from the match.

        Args:
            search_tag (str): the target tag

        Returns: the unified code of all the cells belonging to `search_tag`
        """
        detected = False
        source = ""

        language = _TAGS_LANGUAGE[:]
        language.remove(search_tag)

        for c in self.notebook.cells:
            # parse only source code cells
            if c.cell_type != "code":
                continue
            # in case the previous cell was a `search_tag` cell and this
            # cell is not any other tag of the tag language:
            if detected and (
                ("tags" not in c.metadata or len(c.metadata["tags"]) == 0)
                or all(not any(re.match(tag, t) for t in c.metadata["tags"]) for tag in language)
            ):
                source += "\n" + c.source
            elif (
                "tags" in c.metadata
                and len(c.metadata["tags"]) > 0
                and any(re.match(search_tag, t) for t in c.metadata["tags"])
            ):
                source += "\n" + c.source
                detected = True
            else:
                detected = False
        return source.strip()

    def assign_metrics(self, pipeline_metrics: dict):
        """Assign pipeline metrics to specific pipeline steps.

        This assignment follows a similar logic to the detection of `out`
        dependencies. Starting from a temporary step - child of all the leaf
        nodes, all the nodes in the pipelines are traversed in reversed
        topological order. When a step shows one of the metrics as part of its
        code, then that metric is assigned to the step.

        Args:
            pipeline_metrics (dict): a dict of pipeline metrics where the key
                always the KFP sanitized name and the value the name of the
                original variable.
        """
        # create a temporary step at the end of the pipeline to simplify the
        # iteration from the leaf steps
        tmp_step_name = "_tmp"
        leaf_steps = self.pipeline.get_leaf_steps()
        if not leaf_steps:
            return
        [self.pipeline.add_edge(step.name, tmp_step_name) for step in leaf_steps]

        # pipeline_metrics is a dict having sanitized variable names as keys
        # and the corresponding variable names as values. Here we need to refer
        # to the sanitized names using the python variables.
        # XXX: We could change parse_metrics_print_statements() to return the
        # XXX: reverse dictionary, but that would require changing either
        # XXX: rpc.nb.get_pipeline_metrics() or change in the JupyterLab
        # XXX: Extension parsing of the RPC result
        rev_pipeline_metrics = {v: k for k, v in pipeline_metrics.items()}
        metrics_left = set(rev_pipeline_metrics.keys())
        for anc in graphutils.get_ordered_ancestors(self.pipeline, tmp_step_name):
            if not metrics_left:
                break

            anc_step = self.pipeline.get_step(anc)
            anc_source = "\n".join(anc_step.source)
            # get all the marshal candidates from father's source and intersect
            # with the metrics that have not been matched yet
            marshal_candidates = astutils.get_marshal_candidates(anc_source)
            assigned_metrics = metrics_left.intersection(marshal_candidates)
            # Remove the metrics that have already been assigned.
            metrics_left.difference_update(assigned_metrics)
            # Generate code to produce the metrics artifact in the current step
            if assigned_metrics:
                for target, names in self._metrics_targets(anc_step, assigned_metrics).items():
                    code = METRICS_TEMPLATE % (
                        "    "
                        + ",\n    ".join(
                            [f'"{rev_pipeline_metrics[x]}": {x}' for x in sorted(names)]
                        )
                    )
                    target.source.append(code)
                    # need to have a `metrics` flag set to true in order to set
                    # the metrics output artifact in the pipeline template
                    target.metrics = True
                anc_step.metrics = True

        self.pipeline.remove_node(tmp_step_name)

    @staticmethod
    def _metrics_targets(step: Step, metrics: set) -> dict:
        """Map each step that reports a metric to the metrics it reports.

        A :class:`~kale.step.SubPipeline` emits no component of its own, so a
        metric it provides is reported by the step inside it that computes the
        value. Later steps win, matching the reverse topological order the
        caller walks the graph in.
        """
        if not isinstance(step, SubPipeline):
            return {step: set(metrics)}

        provider = {}
        for inner in step.pipeline.steps:
            provided = set(astutils.get_marshal_candidates("\n".join(inner.source)))
            for name in provided & set(metrics):
                provider[name] = inner

        targets = {}
        for name, inner in provider.items():
            targets.setdefault(inner, set()).add(name)
        return targets

    def _ensure_fns_free_variables(self, anc_step, anc_source: str, imports_and_functions: str):
        """Lazily compute ancestor functions' free vars if missing."""
        if not getattr(anc_step, "fns_free_variables", None):
            anc_step.fns_free_variables = self._detect_fns_free_variables(
                anc_source, imports_and_functions, self.pipeline.pipeline_parameters
            )

    def _propagate_free_vars_from_function(self, step: Step, anc_step: Step, fn_name: str):
        """Helper method.

        Propagate free variables of a function defined in anc_step to
        both the current step's inputs and the ancestor's outputs, including
        nested functions' free variables. Also apply artifact heuristics.
        Additionally, propagate transitive free variables via earlier ancestors
        of anc_step.
        """
        anc_fns_free_vars = getattr(anc_step, "fns_free_variables", {})
        if fn_name not in anc_fns_free_vars:
            return
        fn_free_vars, _ = anc_fns_free_vars[fn_name]
        aggregated = set(fn_free_vars)
        queue = list(fn_free_vars)

        # First, expand using functions defined in the same ancestor
        while queue:
            cur = queue.pop(0)
            if cur in anc_fns_free_vars:
                nested_fv_names, _ = anc_fns_free_vars[cur]
                new_names = set(nested_fv_names) - aggregated
                if new_names:
                    aggregated.update(new_names)
                    queue.extend(list(new_names))

        # Then, expand transitively using functions defined in earlier
        # ancestors of anc_step (i.e., ancestors that lead to anc_step).
        earlier_ancestors = graphutils.get_ordered_ancestors(self.pipeline, anc_step.name)
        for ea_name in earlier_ancestors:
            ea_step = self.pipeline.get_step(ea_name)
            ea_source = "\n".join(ea_step.source)
            # Ensure their fns_free_variables are computed
            self._ensure_fns_free_variables(ea_step, ea_source, self.get_imports_and_functions())
            ea_fns_free_vars = getattr(ea_step, "fns_free_variables", {})
            # We iterate over a snapshot of aggregated to allow growth
            # during the loop
            to_check = list(aggregated)
            idx = 0
            while idx < len(to_check):
                sym = to_check[idx]
                idx += 1
                if sym in ea_fns_free_vars:
                    nested_fv_names, _ = ea_fns_free_vars[sym]
                    for n in nested_fv_names:
                        if n not in aggregated:
                            aggregated.add(n)
                            to_check.append(n)

        # Apply artifact heuristic and update step.ins and anc_step.outs
        # for all aggregated names
        for fv_name in aggregated:
            if fv_name not in step.ins:
                step.ins.append(fv_name)
            inferred_type = "str"
            is_artifact = False
            for key, kfp_type in KFP_ARTIFACT_TYPE_MAP.items():
                if key in fv_name.lower():
                    inferred_type = kfp_type
                    is_artifact = True
                    break
            if is_artifact:
                step.add_artifact(fv_name, inferred_type, is_input=True)
            if fv_name not in anc_step.outs:
                anc_step.outs.append(fv_name)
                if is_artifact:
                    anc_step.add_artifact(fv_name, inferred_type, is_input=False)

    def dependencies_detection(self, imports_and_functions: str = ""):
        """Detects data dependencies between pipeline steps to support KFPv2.

        The data dependencies detection algorithm roughly works as follows:
        1.  Process each step in topological order.
        2.  Identify the `ins` (required variables and their types) for the
         current step. This includes variables from the pipeline's parameters.
        3.  Find functions called within the current step and determine their
         free variables. This is crucial for handling recursive dependencies
         and function calls that rely on external data.
        4.  For each ancestor of the current step, find potential `outs`
         (variables and artifacts) that the current step requires. The
         intersection of the current step's `ins` and the ancestor's potential
         outputs forms a dependency.
        5.  If a function called in the current step was defined in an
         ancestor, ensure its free variables are added to both the current
         step's `ins` and the ancestor's `outs`.
        6.  Detected dependencies are enriched with their associated KFPv2
         artifact types, enabling the compiler to correctly link components.

        Args:
            imports_and_functions: A string containing multiline source-code
            for global imports and functions prepended to every pipeline step.

        Returns:
            An annotated pipeline graph where each step is updated with
            its detected `ins`, `outs`, `parameters`, and `fns_free_variables`
            to facilitate KFP v2 artifact handling.
        """
        # resolve the data dependencies between steps, looping through the
        # graph
        for step in self.pipeline.steps:
            # detect the INS dependencies of the CURRENT node------------------
            step_source = "\n".join(step.source)
            # get the variables that this step is missing and the pipeline
            # parameters that it actually needs.
            ins, parameters = self._detect_in_dependencies(
                source_code=step_source, pipeline_parameters=self.pipeline.pipeline_parameters
            )
            step.parameters = parameters

            fns_free_vars = self._detect_fns_free_variables(
                step_source, imports_and_functions, self.pipeline.pipeline_parameters
            )

            # Get all the function calls. This will be used below to check if
            # any of the ancestors declare any of these functions. Is that is
            # so, the free variables of those functions will have to be loaded.
            fn_calls = astutils.get_function_calls(step_source)
            # add OUT dependencies annotations in the PARENT nodes-------------
            # Intersect the missing names of this father's child with all
            # the father's names. The intersection is the list of variables
            # that the father need to serialize
            # The ancestors are the the nodes that have a path to `step`,
            # ordered by path length.
            ins_left = ins.copy()
            for anc in graphutils.get_ordered_ancestors(self.pipeline, step.name):
                if not ins_left:
                    # if there are no more variables that need to be
                    # marshalled, stop the graph traverse
                    break
                anc_step = self.pipeline.get_step(anc)
                anc_source = "\n".join(anc_step.source)
                # Ensure ancestor's functions free variables are available
                self._ensure_fns_free_variables(anc_step, anc_source, imports_and_functions)
                # get all the marshal candidates from father's source and
                # intersect with the required names of the current node
                marshal_candidates = astutils.get_marshal_candidates(anc_source)
                if isinstance(anc_step, SubPipeline):
                    # a notebook offers what its steps define, not every name
                    # they mention: one it is missing too is not one it can give
                    marshal_candidates -= set(flakeutils.pyflakes_report(code=anc_source))
                outs = ins_left.intersection(marshal_candidates)
                for out_name in outs:
                    # Heuristic for type inference:
                    inferred_type = "str"  # Default
                    is_artifact = False
                    for key, kfp_type in KFP_ARTIFACT_TYPE_MAP.items():
                        if key in out_name.lower():
                            inferred_type = kfp_type
                            is_artifact = True
                            break

                    # Update ancestor's outputs
                    if out_name not in anc_step.outs:
                        anc_step.outs.append(out_name)
                    if is_artifact:
                        anc_step.add_artifact(out_name, inferred_type, is_input=False)

                    # Update current step's inputs for input artifacts
                    if out_name not in step.ins:
                        step.ins.append(out_name)
                    if is_artifact:
                        step.add_artifact(out_name, inferred_type, is_input=True)

                    # This input is satisfied, remove from the set
                    ins_left.remove(out_name)

                    # If the marshaled name is a function defined in the
                    # ancestor, propagate its free variables as additional
                    # ins/outs.
                    self._propagate_free_vars_from_function(step, anc_step, out_name)

                # Include free variables and add them as inputs/outputs
                to_remove_fn_calls = set()
                for fn_call in fn_calls:
                    anc_fns_free_vars = anc_step.fns_free_variables
                    if fn_call in anc_fns_free_vars:
                        # Ensure free vars of the called fn are propagated
                        self._propagate_free_vars_from_function(step, anc_step, fn_call)
                        to_remove_fn_calls.add(fn_call)
                        fns_free_vars[fn_call] = anc_fns_free_vars[fn_call]

                    # Propagate pipeline parameters from the ancestor step
                    # whenever we call a function it provides (directly or via
                    # marshal candidates).
                    if getattr(anc_step, "parameters", None) and (
                        fn_call in anc_fns_free_vars or fn_call in marshal_candidates
                    ):
                        if not hasattr(step, "parameters") or step.parameters is None:
                            step.parameters = {}
                        for _pname, _pval in anc_step.parameters.items():
                            if _pname not in step.parameters:
                                step.parameters[_pname] = _pval

                fn_calls.difference_update(to_remove_fn_calls)
                # finalize bookkeeping for this step
                step.fns_free_variables = fns_free_vars

            # Terminal output artifacts -------------------------------------
            # If the last logical line of the step is a bare variable (the
            # idiomatic Jupyter way of surfacing a value, e.g. a trailing
            # `chroma_db`), promote it to an output artifact even though no
            # descendant step consumes it. Without this, such "result"
            # variables are silently dropped. See kubeflow/kale#783.
            trailing_var = astutils.get_trailing_variable(step_source)
            if (
                trailing_var
                and trailing_var not in step.outs
                and trailing_var in astutils.get_marshal_candidates(step_source)
                and trailing_var not in self.pipeline.pipeline_parameters
            ):
                inferred_type = "Artifact"
                for key, kfp_type in KFP_ARTIFACT_TYPE_MAP.items():
                    if key in trailing_var.lower():
                        inferred_type = kfp_type
                        break
                step.outs.append(trailing_var)
                step.add_artifact(trailing_var, inferred_type, is_input=False)

    def _detect_in_dependencies(self, source_code: str, pipeline_parameters: dict | None = None):
        """Detect missing names from one pipeline step source code.

        Args:
            source_code: Multiline Python source code
            pipeline_parameters: Pipeline parameters dict
        """
        commented_source_code = utils.comment_magic_commands(source_code)
        ins = flakeutils.pyflakes_report(code=commented_source_code)
        # Pipeline parameters will be part of the names that are missing,
        # but of course we don't want to marshal them in as they will be
        # present as parameters
        relevant_parameters = set()
        if pipeline_parameters:
            # Not all pipeline parameters are needed in every pipeline step,
            # these are the parameters that are actually needed by this step.
            relevant_parameters = ins.intersection(pipeline_parameters.keys())
            ins.difference_update(relevant_parameters)
        step_params = (
            {k: pipeline_parameters[k] for k in relevant_parameters} if pipeline_parameters else {}
        )
        return ins, step_params

    def _detect_fns_free_variables(
        self, source_code: str, imports_and_functions: str = "", step_parameters: dict | None = None
    ):
        """Return the function's free variables.

        Free variable: _If a variable is used in a code block but not defined
        there, it is a free variable._

        An Example:

        ```
        x = 5


        def foo():
            print(x)
        ```

        In the example above, `x` is a free variable for function `foo`,
        because it is defined outside of the context of `foo`.

        Here we run the PyFlakes report over the function body to get all the
        missing names (i.e. free variables), excluding the function arguments.

        Args:
            source_code: Multiline Python source code
            imports_and_functions: Multiline Python source that is prepended
                to every pipeline step. It should contain the code cells that
                where tagged as `import` and `functions`. We prepend this code
                to the function body because it will always be present in any
                pipeline step.
            step_parameters: Step parameters names. The step parameters
                are removed from the pyflakes report, as these names will
                always be available in the step's context.

        Returns (dict): A dictionary with the name of the function as key and
            a list of variables names + consumed pipeline parameters as values.
        """
        fns_free_vars = {}
        # now check the functions' bodies for free variables. fns is a
        # dict function_name -> function_source
        fns = astutils.parse_functions(source_code)
        for fn_name, fn in fns.items():
            code = imports_and_functions + "\n" + fn
            free_vars = flakeutils.pyflakes_report(code=code)
            # the pipeline parameters that are used in the function
            consumed_params = {}
            if step_parameters:
                consumed_params = free_vars.intersection(step_parameters.keys())
                # remove the used parameters form the free variables, as they
                # need to be handled differently.
                free_vars.difference_update(consumed_params)
            fns_free_vars[fn_name] = (free_vars, consumed_params)
        return fns_free_vars
