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
"""Compile a Kale :class:`~kale.pipeline.Pipeline` into a Kubeflow Pipelines v2 DSL script.

This module renders the Jinja2 templates in ``kale/templates/`` to produce a
ready-to-run KFP v2 pipeline script, formats it, and optionally hands it off to
the KFP SDK for compilation and submission.
"""

import argparse
import logging
import os
import re
from typing import NamedTuple

import autopep8
from jinja2 import Environment, FileSystemLoader, PackageLoader

from kale import __version__ as KALE_VERSION
from kale.common import graphutils, k8sutils, kfputils, podutils, utils
from kale.common.imports import get_packages_to_install
from kale.pipeline import DEFAULT_BASE_IMAGE, Pipeline, PipelineParam, Step
from kale.step import SubPipeline

log = logging.getLogger(__name__)

NB_FN_TEMPLATE = "nb_function_template.jinja2"
PIPELINE_TEMPLATE = "pipeline_template.jinja2"

# Generated DSL modules are named after their notebook, behind this prefix, so
# that a notebook called `json.ipynb` cannot shadow a module the DSL imports.
MODULE_PREFIX = "kale_notebook_"


def to_kale_env_var_name(pvc_name: str) -> str:
    """Derive a KALE_VOLUME_<NAME> env var name from a PVC name.

    Non-alphanumeric characters are collapsed to ``_``. This mapping is lossy
    for DNS subdomain names (both ``-`` and ``.`` become ``_``), so callers
    that expose multiple volumes must ensure the derived names stay unique.
    """
    return "KALE_VOLUME_" + re.sub(r"[^A-Z0-9]", "_", pvc_name.upper())


KFP_DSL_ARTIFACT_IMPORTS = [
    "Dataset",
    "Model",
    "Metrics",
    "ClassificationMetrics",
    "Artifact",
    "HTML",
]


class Artifact(NamedTuple):
    """A Step artifact."""

    name: str
    type: str
    is_input: bool = False


def _artifact_type(var_name: str) -> str:
    """KFP artifact type inferred from a variable's name."""
    return "Model" if "model" in var_name else "Dataset"


def _clean_param_name(param_name: str) -> str:
    """Name a pipeline parameter is passed to a component under."""
    return f"{param_name.lower()}_param" if param_name.isupper() else param_name


def _step_display_name(step_name: str) -> str:
    """Name a step is shown under, the same whether or not it is composed."""
    return f"{step_name.replace('_', '-')}-step"


def _module_name(root_name: str, reference_name: str) -> str:
    """Module a referenced notebook is generated into.

    The root is part of the name because two notebooks in one directory can
    reference different notebooks under the same name, and their modules are
    written side by side.
    """
    return f"{MODULE_PREFIX}{root_name}_{reference_name}".replace("-", "_")


class Compiler:
    """Converts a Pipeline object into a KFP executable.

    Compiler provides the tools to convert a Pipeline object into an
    executable script that uses the KFP DSL to create and upload a
    new pipeline.

    The Pipeline object is assumed to provide all the necessary information
    (environment, configuration, etc...) for the script to be compiled.
    """

    def __init__(self, pipeline: Pipeline, imports_and_functions: str):
        self.pipeline = pipeline
        self.templating_env = None
        self.dsl_source = ""
        self.dsl_script_path = None
        self.imports_and_functions = imports_and_functions
        # module name -> source, for the notebooks this pipeline references
        self.modules: dict[str, str] = {}

    @staticmethod
    def _get_args():
        parser = argparse.ArgumentParser(description="Run Kale Pipeline")
        parser.add_argument("-K", "--kfp", action="store_true")
        return parser.parse_args()

    def compile_and_run(self):
        """First compile the Pipeline to DSL and then run it."""
        self.compile()
        self.run()

    def compile(self):
        """Convert Pipeline to KFP DSL.

        Returns path to DSL script.
        """
        log.info("Compiling Pipeline into KFP DSL code")
        self._check_unique_volume_env_vars()
        self._warn_rwo_volumes()
        self.dsl_source = self.generate_dsl()
        return self._save_compiled_code()

    def _check_unique_volume_env_vars(self):
        """Fail compile if exposed volume env var names collide.

        ``to_kale_env_var_name`` maps every non-alphanumeric character to ``_``,
        so distinct PVC names (e.g. ``my-data`` / ``my.data``) can produce the
        same ``KALE_VOLUME_*`` name. Detect that before emitting DSL so one
        volume cannot silently overwrite another's env var at runtime.
        """
        seen = {}
        for vol in self.pipeline.config.volumes or []:
            if not getattr(vol, "expose_as_env_var", False):
                continue
            env_name = to_kale_env_var_name(vol.name)
            if env_name in seen:
                raise ValueError(
                    f"Volumes '{seen[env_name]}' and '{vol.name}' both derive "
                    f"env var '{env_name}'. Rename one of the PVCs or disable "
                    "'Expose mount path as env var' on one of them."
                )
            seen[env_name] = vol.name

    def _warn_rwo_volumes(self):
        """Emit a warning at compile time for any RWO PVC volumes.

        RWO volumes can only be mounted on one node at a time.  If pipeline
        steps are scheduled on different nodes they will fail to mount.  We
        check at compile time (where we have cluster access) so the warning
        appears immediately in the Kale output rather than buried in pod logs.
        """
        pvc_volumes = [
            v for v in self.pipeline.config.volumes or [] if getattr(v, "type", None) == "pvc"
        ]
        if not pvc_volumes:
            return
        try:
            namespace = podutils.get_namespace()
        except Exception:
            return
        for vol in pvc_volumes:
            try:
                modes = k8sutils.get_pvc_access_modes(vol.name, namespace)
            except Exception:
                continue
            if "ReadWriteOnce" in modes:
                log.warning(
                    "[KALE WARNING] PVC '%s' has accessMode ReadWriteOnce. "
                    "If pipeline steps run on different nodes, concurrent "
                    "mounts will fail.",
                    vol.name,
                )

    def run(self):
        """Run the generated KFP script."""
        if not self.dsl_script_path:
            raise RuntimeError(
                "The Compiler has yet to generate a new KFP"
                " DSL script. Please run the `compile` function"
                " first."
            )
        self._run_compiled_code(self.dsl_script_path)

    def generate_dsl(self):
        """Generate a Python KFP DSL executable starting from the pipeline.

        Returns (str): A Python executable script
        """
        # Fail early if there are no steps in the pipeline.
        if not hasattr(self.pipeline, "steps") or not self.pipeline.steps:
            raise ValueError("Task is missing from pipeline.")

        nodes = list(self.pipeline.steps)
        if any(isinstance(node, SubPipeline) for node in nodes):
            return self.generate_composition(nodes)

        # List of lightweight components generated code
        lightweight_components = [self.generate_lightweight_component(step) for step in nodes]
        pipeline_code = self.generate_pipeline(lightweight_components)
        return pipeline_code

    def generate_composition(self, nodes):
        """Generate the DSL for a pipeline that references other notebooks.

        Every referenced notebook becomes an importable module of its own,
        holding its components and a nested pipeline, and this notebook's DSL
        imports them and wires them together with its own steps. The modules
        are written next to it by :meth:`_save_compiled_code`.
        """
        for node in nodes:
            if isinstance(node, SubPipeline):
                self.modules[self._module_name(node)] = autopep8.fix_code(
                    self._render_pipeline(**self._subpipeline_context(node))
                )

        parameters = self._parameter_context()
        components, calls = [], []
        for node in nodes:
            after = [
                self._task_var(self.pipeline.get_step(p))
                for p in self.pipeline.predecessors(node.name)
            ]
            inputs = [
                {"arg": f"{var}_input_artifact", "ref": self._boundary_ref(node, var)}
                for var in sorted(node.ins)
            ]
            is_subpipeline = isinstance(node, SubPipeline)
            if not is_subpipeline:
                # a referenced notebook declares its own parameters; these are
                # this notebook's, so they go to its own steps
                inputs.extend({"arg": p["arg"], "ref": p["name"]} for p in parameters)
            calls.append(
                {
                    "task_var": self._task_var(node),
                    "fn": f"{self._module_name(node)}_pipeline"
                    if is_subpipeline
                    else f"{node.name}_step",
                    "inputs": inputs,
                    "after": sorted(set(after)),
                    "display": node.display_name
                    if is_subpipeline
                    else _step_display_name(node.name),
                    "node": node,
                    # a nested pipeline is not a pod, so it takes no security
                    # context; its own steps get one inside their module
                    "is_component": not is_subpipeline,
                }
            )
            if not is_subpipeline:
                # after the call is recorded: generating the component rewrites
                # step.source
                components.append(autopep8.fix_code(self.generate_lightweight_component(node)))

        return self._render_pipeline(
            fn="auto_generated_pipeline",
            pipeline_name=self.pipeline.config.pipeline_name,
            pipeline_description=self.pipeline.config.pipeline_description
            or "Composed from: " + ", ".join(n.name for n in nodes),
            docstring=(
                "Composed pipeline: each referenced notebook is its own "
                "sub-pipeline (sub-DAG); this notebook's own steps are "
                "top-level components."
            ),
            signature=self._signature(parameters),
            tasks=calls,
            components=components,
            modules=[self._module_name(n) for n in nodes if isinstance(n, SubPipeline)],
        )

    def _render_pipeline(
        self,
        *,
        fn,
        pipeline_name,
        pipeline_description,
        docstring,
        signature,
        tasks,
        components,
        modules=(),
        returns=(),
    ):
        """Render one pipeline function, whatever it is a pipeline of.

        A root notebook, a referenced notebook and the notebook that composes
        them are all the same shape: a signature, a list of tasks with their
        wiring, and optionally some outputs. What differs between them is how
        the wiring is worked out, which is the caller's job, not the template's.
        """
        return (
            self._get_templating_env()
            .get_template(PIPELINE_TEMPLATE)
            .render(
                fn=fn,
                pipeline_name=pipeline_name,
                pipeline_description=pipeline_description,
                docstring=docstring,
                signature=signature,
                tasks=tasks,
                components=components,
                modules=modules,
                returns=returns,
                enable_caching=self.pipeline.config.enable_caching,
                security_context=self.pipeline.config.security_context,
                volumes=self.pipeline.config.volumes,
            )
        )

    @staticmethod
    def _signature(parameters, artifacts=()):
        """Parameter list of a generated pipeline function.

        Artifact inputs come first: they have no default, and a referenced
        notebook's parameters do.
        """
        return ", ".join(
            list(artifacts) + [f"{p['name']}: {p['type']} = {p['default']}" for p in parameters]
        )

    def _parameter_context(self):
        """The pipeline's parameters, as they appear in the generated code.

        ``name`` is the variable a pipeline function declares, ``arg`` the
        keyword a component receives it under.
        """
        parameters = []
        for param_name, param in getattr(self.pipeline, "pipeline_parameters", {}).items():
            if isinstance(param, PipelineParam):
                parameters.append(
                    {
                        "name": param_name.lower(),
                        "arg": _clean_param_name(param_name),
                        "type": param.param_type or "str",
                        "default": repr(param.param_value),
                    }
                )
        return parameters

    def _subpipeline_context(self, node):
        """Template context for one referenced notebook's module.

        The components are generated by a compiler bound to the referenced
        notebook's own pipeline, so its pipeline parameters and its imports are
        the ones its steps are built with, exactly as when it is compiled on its
        own. Caching and security context are the exception: those are global to
        a composition and come from the root notebook.
        """
        inner = list(node.pipeline.steps)
        owner = Compiler(node.pipeline, node.imports_and_functions)
        parameters = owner._parameter_context()
        tasks = []
        components = []
        for step in inner:
            after, inputs = [], []
            for var in sorted(step.ins):
                if var in node.ins:
                    ref = f"{var}_input_artifact"
                else:
                    producer = self._inner_producer(node, inner, step, var)
                    ref = f'{producer}_task.outputs["{var}_output_artifact"]'
                    after.append(f"{producer}_task")
                inputs.append({"arg": f"{var}_input_artifact", "ref": ref})
            # every component takes the whole parameter set, as it does when the
            # notebook is compiled on its own
            inputs.extend({"arg": p["arg"], "ref": p["name"]} for p in parameters)
            tasks.append(
                {
                    "task_var": f"{step.name}_task",
                    "fn": f"{step.name}_step",
                    "inputs": inputs,
                    "after": sorted(set(after)),
                    "display": _step_display_name(step.name),
                    "node": step,
                    "is_component": True,
                }
            )
            # after the task is recorded: generating the component rewrites
            # step.source
            components.append(owner.generate_lightweight_component(step))
        artifact_params = [
            f"{var}_input_artifact: Input[{_artifact_type(var)}]" for var in sorted(node.ins)
        ]
        return {
            "fn": f"{self._module_name(node)}_pipeline",
            "pipeline_name": node.display_name,
            "pipeline_description": f"Compiled from notebook {node.display_name}.",
            "docstring": f"Sub-pipeline compiled from notebook '{node.display_name}'.",
            "signature": self._signature(parameters, artifact_params),
            "tasks": tasks,
            "components": components,
            "returns": [
                {
                    "var": var,
                    "type": _artifact_type(var),
                    "ref": f'{node.produced_by[var]}_task.outputs["{var}_output_artifact"]',
                }
                for var in sorted(node.outs)
            ],
        }

    @staticmethod
    def _inner_producer(node, inner, consumer, var):
        """Step of the same notebook that produces ``var`` for ``consumer``."""
        producer = None
        for step in inner:
            if step.name == consumer.name:
                break
            if var in step.outs:
                producer = step.name
        if producer is None:
            raise ValueError(
                f"Step '{consumer.name}' of '{node.name}' requires '{var}', but no earlier "
                f"step of that notebook produces it."
            )
        return producer

    def _task_var(self, node):
        """Task variable of a node in the generated pipeline.

        A referenced notebook uses its module name, so a notebook whose file
        name is not a valid Python identifier still yields valid code.
        """
        if isinstance(node, SubPipeline):
            return f"{self._module_name(node)}_task"
        return f"{node.name}_task"

    def _module_name(self, node):
        """Module the referenced notebook of ``node`` is generated into.

        Keyed on the root notebook rather than on its pipeline name: file names
        are necessarily unique within a directory, pipeline names are not.
        """
        return _module_name(self._root_name(), node.name)

    def _root_name(self) -> str:
        """Name identifying the notebook being compiled, for generated files."""
        notebook = getattr(self.pipeline.config, "notebook_path", "")
        if notebook:
            return utils.sanitize_k8s_name(os.path.splitext(os.path.basename(notebook))[0])
        return self.pipeline.config.pipeline_name

    def _boundary_ref(self, node, var):
        """Reference to the task output that satisfies ``var`` for ``node``."""
        for name in self.pipeline.predecessors(node.name):
            producer = self.pipeline.get_step(name)
            if var not in producer.outs:
                continue
            task = self._task_var(producer)
            if not isinstance(producer, SubPipeline):
                # a component exposes each output artifact by parameter name
                return f'{task}.outputs["{var}_output_artifact"]'
            # one nested output is reachable as `.output`; several become a
            # NamedTuple addressed by field name
            if len(producer.outs) > 1:
                return f'{task}.outputs["{var}"]'
            return f"{task}.output"
        raise ValueError(
            f"'{node.name}' requires '{var}', but none of the units above it produces it."
        )

    def generate_lightweight_component(self, step: Step):
        """Generate Python code using the notebook function template."""
        step_source_raw = step.source

        def _encode_source(s):
            # Encode line by line a multiline string
            return "\n    ".join(
                [line.encode("unicode_escape").decode("utf-8") for line in s.splitlines()]
            )

        # Since the code will be wrapped in triple quotes inside the
        # template, we need to escape triple quotes as they will not be
        # escaped by encode("unicode_escape").
        step.source = [re.sub(r"'''", "\\'\\'\\'", _encode_source(s)) for s in step_source_raw]

        template = self._get_templating_env().get_template(NB_FN_TEMPLATE)

        # Separate parameters with and without defaults for proper ordering
        params_without_defaults = []

        # Add HTML report output only if not explicitly disabled
        if step.config.generate_html_report is not False:
            params_without_defaults.append(f"{step.name}_html_report: Output[HTML]")

        if hasattr(step, "metrics") and step.metrics:
            params_without_defaults.append("kale_metrics_artifact: Output[Metrics]")

        params_with_defaults = []
        step_inputs_list, step_outputs_list = [], []
        if hasattr(step, "ins") and step.ins:
            step_inputs_list = sorted(step.ins)
            for var_name in step_inputs_list:
                input_type = _artifact_type(var_name)
                params_without_defaults.append(f"{var_name}_input_artifact: Input[{input_type}]")

        step_outputs_list = []

        if hasattr(step, "outs") and step.outs:
            step_outputs_list = sorted(step.outs)
            for var_name in step_outputs_list:
                output_type = _artifact_type(var_name)
                params_without_defaults.append(f"{var_name}_output_artifact: Output[{output_type}]")

        if hasattr(self.pipeline, "pipeline_parameters") and self.pipeline.pipeline_parameters:  # noqa: E501
            for param_name, param in self.pipeline.pipeline_parameters.items():
                if isinstance(param, PipelineParam):
                    param_type = param.param_type or "str"
                    param_value_str = repr(param.param_value)
                    clean_param_name = _clean_param_name(param_name)
                    params_with_defaults.append(
                        f"{clean_param_name}: {param_type} = {param_value_str}"
                    )

        component_params_list = params_without_defaults + params_with_defaults
        component_signature_args = ", ".join(component_params_list)

        # Create pipeline parameter mapping for the template
        pipeline_params = {}
        if hasattr(self.pipeline, "pipeline_parameters") and self.pipeline.pipeline_parameters:  # noqa: E501
            for param_name, param in self.pipeline.pipeline_parameters.items():
                if isinstance(param, PipelineParam):
                    clean_param_name = _clean_param_name(param_name)
                    param = {clean_param_name: param.param_value}
                    pipeline_params[param_name] = param

        # Create step artifacts info for template
        step_inputs = []
        step_outputs = []

        for var_name in step_inputs_list:
            input_type = _artifact_type(var_name)
            step_inputs.append(Artifact(name=f"{var_name}", type=input_type, is_input=True))

        for var_name in step_outputs_list:
            output_type = _artifact_type(var_name)
            step_outputs.append(Artifact(name=f"{var_name}", type=output_type, is_input=False))

        packages_list = self._get_package_list_from_imports()
        pip_index_urls = utils.compute_pip_index_urls()
        pip_trusted_hosts = utils.compute_trusted_hosts()
        fn_code = template.render(
            pip_index_urls=pip_index_urls,
            pip_trusted_hosts=pip_trusted_hosts,
            step=step,
            component_signature_args=component_signature_args,
            pipeline_params=pipeline_params,
            packages_list=packages_list,
            step_inputs=step_inputs,
            step_outputs=step_outputs,
            kfp_dsl_artifact_imports=KFP_DSL_ARTIFACT_IMPORTS,
            default_base_image=DEFAULT_BASE_IMAGE,
            **self.pipeline.config.to_dict(),
        )
        return autopep8.fix_code(fn_code)

    def generate_pipeline(self, lightweight_components):
        """Generate Python code using the pipeline template."""
        parameters = self._parameter_context()
        param_inputs = [{"arg": p["arg"], "ref": p["name"]} for p in parameters]

        steps = list(self.pipeline.steps)
        tasks = []
        for position, step in enumerate(steps):
            inputs, after = [], []
            for var in sorted(getattr(step, "ins", []) or []):
                producer = self._producer_of(step, var)
                inputs.append(
                    {
                        "arg": f"{var}_input_artifact",
                        "ref": f'{producer}_task.outputs["{var}_output_artifact"]',
                    }
                )
                after.append(f"{producer}_task")
            if not after and position > 0:
                # nothing flows in, so the step runs after the one above it
                after = [f"{steps[position - 1].name}_task"]
            tasks.append(
                {
                    "task_var": f"{step.name}_task",
                    "fn": f"{step.name}_step",
                    "inputs": inputs + param_inputs,
                    "after": sorted(set(after)),
                    "display": _step_display_name(step.name),
                    "node": step,
                    "is_component": True,
                }
            )

        pipeline_code = self._render_pipeline(
            fn="auto_generated_pipeline",
            pipeline_name=self.pipeline.config.pipeline_name,
            pipeline_description=self.pipeline.config.pipeline_description,
            docstring="Auto-generated pipeline function.",
            signature=self._signature(parameters),
            tasks=tasks,
            components=lightweight_components,
        )
        # fix code style using pep8 guidelines
        return autopep8.fix_code(pipeline_code)

    def _producer_of(self, step, var):
        """Name of the ancestor step that provides ``var`` to ``step``."""
        for name in graphutils.get_ordered_ancestors(self.pipeline, step.name):
            if var in (getattr(self.pipeline.get_step(name), "outs", []) or []):
                return name
        return "UNKNOWN"

    def _get_package_list_from_imports(self):
        """Extract pip-installable package names from imports using AST.

        Uses the imports module to parse Python import statements via AST
        and resolve them to their corresponding PyPI package names. This
        properly handles all import forms and filters out stdlib modules.

        Returns:
            A sorted list of unique PyPI package names to install.
        """
        package_names = set()

        # Always include kale and kfp as dependencies
        if KALE_VERSION != "0+unknown":
            package_names.add(f"kubeflow-kale=={KALE_VERSION}")
        else:
            package_names.add("kubeflow-kale")
        package_names.add("kfp>=2.0.0")

        # Parse imports using AST and resolve to PyPI package names
        package_names.update(get_packages_to_install(self.imports_and_functions))

        return sorted(package_names)

    def _get_templating_env(self, templates_path=None):
        if self.templating_env:
            return self.templating_env

        if templates_path:
            loader = FileSystemLoader(templates_path)
        else:
            loader = PackageLoader("kale", "templates")
        template_env = Environment(loader=loader)
        # add custom filters
        template_env.filters["add_suffix"] = lambda s, suffix: s + suffix
        template_env.filters["add_prefix"] = lambda s, prefix: prefix + s
        template_env.filters["quote_if_not_none"] = lambda x: f'"{x}"' if x is not None else None
        # Derive KALE_VOLUME_<NAME> env var name from a PVC name.
        template_env.filters["to_kale_env_var_name"] = to_kale_env_var_name
        self.templating_env = template_env
        return template_env

    def _save_compiled_code(self, path: str = None) -> str:
        if not path:
            config_output_path = self.pipeline.config.output_path
            if config_output_path:
                # Resolve relative to CWD (the notebook's working directory)
                path = os.path.join(os.getcwd(), config_output_path)
            else:
                # Default: save in hidden .kale/ directory
                path = os.path.join(os.getcwd(), ".kale")
        os.makedirs(path, exist_ok=True)
        log.info("Saving generated code in %s", path)
        # a referenced notebook is an importable module of its own, written
        # next to the pipeline that imports it
        for module_name, source in self.modules.items():
            with open(os.path.join(path, f"{module_name}.py"), "w") as f:
                f.write(source)
        filename = f"{self.pipeline.config.pipeline_name}.kale.py"
        output_path = os.path.abspath(os.path.join(path, filename))
        with open(output_path, "w") as f:
            f.write(self.dsl_source)
        log.info("Successfully saved generated code: %s", output_path)
        self.dsl_script_path = output_path
        return output_path

    def _run_compiled_code(self, script_path: str):
        pipeline_name = self.pipeline.config.pipeline_name
        pipeline_yaml_path = kfputils.compile_pipeline(script_path, pipeline_name)
        pipeline_id, version_id = kfputils.upload_pipeline(pipeline_yaml_path, pipeline_name)
        kfputils.run_pipeline(
            experiment_name=self.pipeline.config.experiment_name,
            pipeline_id=pipeline_id,
            version_id=version_id,
        )
