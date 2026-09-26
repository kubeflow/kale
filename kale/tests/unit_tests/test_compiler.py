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

from types import SimpleNamespace

import pytest

from kale.compiler import Compiler, _parameters_of, to_kale_env_var_name
from kale.step import PipelineParam


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


def _pipeline_with_params(names):
    """Build a pipeline stub whose pipeline_parameters are the given names."""
    return SimpleNamespace(
        pipeline_parameters={n: PipelineParam("int", i) for i, n in enumerate(names)}
    )


def test_pipeline_signature_keeps_parameter_case():
    """Parameters differing only in case stay distinct in the pipeline signature."""
    parameters = _parameters_of(_pipeline_with_params(["a", "A"]))
    signature = Compiler._signature(parameters)

    assert signature == "a: int = 0, A: int = 1"
    compile(f"def pipeline({signature}): pass", "<signature>", "exec")


def _compiler_with_params(names):
    """Build a bare Compiler whose pipeline has the given parameter names."""
    compiler = Compiler.__new__(Compiler)
    compiler.pipeline = _pipeline_with_params(names)
    return compiler


def test_check_unique_param_names_allows_case_variants():
    """Parameters differing only in case derive distinct argument names."""
    _compiler_with_params(["a", "A"])._check_unique_param_names()


def test_check_unique_param_names_raises_on_collision():
    """Parameters deriving the same argument name raise ValueError at compile time."""
    compiler = _compiler_with_params(["A", "a_param"])
    with pytest.raises(ValueError, match=r"'A' and 'a_param'.*'a_param'"):
        compiler._check_unique_param_names()
