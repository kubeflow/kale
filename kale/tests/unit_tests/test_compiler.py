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

import ast
from types import SimpleNamespace

import nbformat
import pytest

from kale.compiler import Compiler, to_kale_env_var_name
from kale.processors import NotebookProcessor


def _get_env_var_name_filter():
    """Return the to_kale_env_var_name Jinja2 filter from the Compiler env."""
    compiler = Compiler.__new__(Compiler)
    compiler.templating_env = None
    env = compiler._get_templating_env()
    return env.filters["to_kale_env_var_name"]


@pytest.mark.parametrize(
    "pvc_name,expected",
    [
        ("raw-data", "KALE_VOLUME_RAW_DATA"),
        ("my.pvc", "KALE_VOLUME_MY_PVC"),
        ("data123", "KALE_VOLUME_DATA123"),
        ("UPPER", "KALE_VOLUME_UPPER"),
        ("a-b_c.d/e", "KALE_VOLUME_A_B_C_D_E"),
        ("single", "KALE_VOLUME_SINGLE"),
    ],
)
def test_to_kale_env_var_name(pvc_name, expected):
    """to_kale_env_var_name converts PVC names to KALE_VOLUME_<NAME> env var names."""
    assert to_kale_env_var_name(pvc_name) == expected
    assert _get_env_var_name_filter()(pvc_name) == expected


def _compiler_with_volumes(volumes):
    """Build a bare Compiler whose pipeline.config.volumes is the given list."""
    compiler = Compiler.__new__(Compiler)
    compiler.pipeline = SimpleNamespace(config=SimpleNamespace(volumes=volumes))
    return compiler


def test_check_unique_volume_env_vars_allows_distinct_names():
    """Distinct derived env var names pass the uniqueness check."""
    compiler = _compiler_with_volumes(
        [
            SimpleNamespace(name="raw-data", expose_as_env_var=True),
            SimpleNamespace(name="model-store", expose_as_env_var=True),
            SimpleNamespace(name="raw.data", expose_as_env_var=False),
        ]
    )
    compiler._check_unique_volume_env_vars()


def test_check_unique_volume_env_vars_raises_on_collision():
    """Colliding derived env var names raise ValueError at compile time."""
    compiler = _compiler_with_volumes(
        [
            SimpleNamespace(name="my-data", expose_as_env_var=True),
            SimpleNamespace(name="my.data", expose_as_env_var=True),
        ]
    )
    with pytest.raises(ValueError, match=r"my-data.*my\.data.*KALE_VOLUME_MY_DATA"):
        compiler._check_unique_volume_env_vars()


def test_check_unique_volume_env_vars_ignores_unexposed_volumes():
    """Volumes without expose_as_env_var do not participate in the collision check."""
    compiler = _compiler_with_volumes(
        [
            SimpleNamespace(name="my-data", expose_as_env_var=True),
            SimpleNamespace(name="my.data", expose_as_env_var=False),
        ]
    )
    compiler._check_unique_volume_env_vars()


def test_annotation_and_label_values_are_escaped_in_dsl(tmp_path, monkeypatch):
    """Values that contain ':' or '"' must survive into a DSL that still parses."""
    nb = nbformat.v4.new_notebook()
    nb.metadata["kubeflow_notebook"] = {
        "pipeline_name": "annotations",
        "experiment_name": "test",
        "volumes": [],
    }
    cell = nbformat.v4.new_code_cell(source="x = 1")
    cell.metadata["tags"] = [
        "step:train",
        "annotation:example.com/dashboard:http://grafana.local:3000/d/abc",
        'annotation:example.com/config:{"lr": 0.01}',
        "label:team:ml",
    ]
    nb.cells.append(cell)
    nb_path = tmp_path / "annotations.ipynb"
    nbformat.write(nb, str(nb_path))
    monkeypatch.chdir(tmp_path)

    processor = NotebookProcessor(
        str(nb_path), {"pipeline_name": "annotations", "experiment_name": "test"}
    )
    pipeline = processor.run()
    dsl_path = Compiler(pipeline, processor.get_imports_and_functions()).compile()
    dsl = open(dsl_path).read()

    calls = {}
    for node in ast.walk(ast.parse(dsl)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) in (
            "add_pod_annotation",
            "add_pod_label",
        ):
            kw = {k.arg: ast.literal_eval(k.value) for k in node.keywords if k.arg != "task"}
            calls[kw.get("annotation_key", kw.get("label_key"))] = kw.get(
                "annotation_value", kw.get("label_value")
            )

    assert calls == {
        "example.com/dashboard": "http://grafana.local:3000/d/abc",
        "example.com/config": '{"lr": 0.01}',
        "team": "ml",
    }
