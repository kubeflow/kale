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

import pytest

from kale import Pipeline, Step
import kale.common.flakeutils


@pytest.mark.parametrize(
    "code,target",
    [
        ("", []),
        ("a = b", ["b"]),
        ("a = foo(b)", ["foo", "b"]),
        ("a = b\nfoo(b)", ["b", "foo"]),
        ("foo(b)", ["foo", "b"]),
    ],
)
def test_pyflakes_report(code, target):
    """Tests pyflakes_report function."""
    res = kale.common.flakeutils.pyflakes_report(code)
    assert sorted(res) == sorted(target)


def test_detect_fns_free_variables(notebook_processor):
    """Test the function returns the correct free variables."""
    source_code = """
x = 5
def foo():
    print(math.sqrt(x))
    """

    target = {"foo": ({"x", "math"}, {})}
    assert target == notebook_processor._detect_fns_free_variables(source_code)


def test_detect_fns_free_variables_with_imports(notebook_processor):
    """Test the function returns the correct free variables."""
    imports_and_functions = """
import math
    """

    source_code = """
x = 5
def foo():
    print(math.sqrt(x))
    """

    target = {"foo": ({"x"}, {})}
    assert target == notebook_processor._detect_fns_free_variables(
        source_code, imports_and_functions
    )


def _prepend_to_source(source, prefix):
    return [prefix + "\n" + "\n".join(source)]


def test_dependencies_detection_free_variable(notebook_processor, dummy_nb_config):
    """Test dependencies detection with free variables."""
    pipeline = Pipeline(dummy_nb_config)

    _source = [
        """
x = 5
"""
    ]
    pipeline.add_step(Step(name="step1", source=_source))

    _source = [
        """
def foo():
   print(x)
"""
    ]
    pipeline.add_step(Step(name="step2", source=_source))

    _source = [
        """
foo()
"""
    ]
    pipeline.add_step(Step(name="step3", source=_source))

    pipeline.add_edge("step1", "step2")
    pipeline.add_edge("step2", "step3")

    notebook_processor.pipeline = pipeline
    notebook_processor.dependencies_detection()
    assert sorted(pipeline.get_step("step1").ins) == []
    assert sorted(pipeline.get_step("step1").outs) == ["x"]
    assert sorted(pipeline.get_step("step2").ins) == ["x"]
    assert sorted(pipeline.get_step("step2").outs) == ["foo", "x"]
    assert sorted(pipeline.get_step("step3").ins) == ["foo", "x"]
    assert sorted(pipeline.get_step("step3").outs) == []


def test_dependencies_detection_inner_function(notebook_processor, dummy_nb_config):
    """Test dependencies detection with inner functions."""
    pipeline = Pipeline(dummy_nb_config)

    _source = ["x = 5"]
    pipeline.add_step(Step(name="step1", source=_source))
    _source = [
        """
def foo():
    def bar(x):
        print(x)
    bar(5)
"""
    ]
    pipeline.add_step(Step(name="step2", source=_source))
    _source = [
        """
foo()
print(x)
"""
    ]
    pipeline.add_step(Step(name="step3", source=_source))

    pipeline.add_edge("step1", "step2")
    pipeline.add_edge("step2", "step3")

    notebook_processor.pipeline = pipeline
    notebook_processor.dependencies_detection()
    assert sorted(pipeline.get_step("step1").ins) == []
    assert sorted(pipeline.get_step("step1").outs) == ["x"]
    assert sorted(pipeline.get_step("step2").ins) == []
    assert sorted(pipeline.get_step("step2").outs) == ["foo"]
    assert sorted(pipeline.get_step("step3").ins) == ["foo", "x"]
    assert sorted(pipeline.get_step("step3").outs) == []


def test_dependencies_detection_inner_function_free_variable(notebook_processor, dummy_nb_config):
    """Test dependencies detection with free variables and inner function."""
    pipeline = Pipeline(dummy_nb_config)

    _source = ["x = 5"]
    pipeline.add_step(Step(name="step1", source=_source))
    _source = [
        """
def foo():
    def bar():
        print(x)
"""
    ]
    pipeline.add_step(Step(name="step2", source=_source))
    _source = ["foo()"]
    pipeline.add_step(Step(name="step3", source=_source))

    pipeline.add_edge("step1", "step2")
    pipeline.add_edge("step2", "step3")

    notebook_processor.pipeline = pipeline
    notebook_processor.dependencies_detection()
    assert sorted(pipeline.get_step("step1").ins) == []
    assert sorted(pipeline.get_step("step1").outs) == ["x"]
    assert sorted(pipeline.get_step("step2").ins) == ["x"]
    assert sorted(pipeline.get_step("step2").outs) == ["foo", "x"]
    assert sorted(pipeline.get_step("step3").ins) == ["foo", "x"]
    assert sorted(pipeline.get_step("step3").outs) == []


def test_dependencies_detection_with_parameter(notebook_processor, dummy_nb_config):
    """Test dependencies detection with function with parameter."""
    pipeline = Pipeline(dummy_nb_config)

    _source = ["x = 5"]
    pipeline.add_step(Step(name="step1", source=_source))
    _source = [
        """
def foo(x):
    def bar():
        print(x)
"""
    ]
    pipeline.add_step(Step(name="step2", source=_source))
    _source = ["foo(5)"]
    pipeline.add_step(Step(name="step3", source=_source))

    pipeline.add_edge("step1", "step2")
    pipeline.add_edge("step2", "step3")

    notebook_processor.pipeline = pipeline
    notebook_processor.dependencies_detection()
    assert sorted(pipeline.get_step("step1").ins) == []
    assert sorted(pipeline.get_step("step1").outs) == []
    assert sorted(pipeline.get_step("step2").ins) == []
    assert sorted(pipeline.get_step("step2").outs) == ["foo"]
    assert sorted(pipeline.get_step("step3").ins) == ["foo"]
    assert sorted(pipeline.get_step("step3").outs) == []


def test_dependencies_detection_with_globals(notebook_processor, dummy_nb_config):
    """Test dependencies detection with inner function and globals."""
    imports_and_functions = "import math"

    pipeline = Pipeline(dummy_nb_config)

    _source = ["x = 5"]
    pipeline.add_step(Step(name="step1", source=_prepend_to_source(_source, imports_and_functions)))
    _source = [
        """
def foo(x):
    def bar():
        math.sqrt(x)
    bar()
"""
    ]
    pipeline.add_step(Step(name="step2", source=_prepend_to_source(_source, imports_and_functions)))
    _source = ["foo(5)"]
    pipeline.add_step(Step(name="step3", source=_prepend_to_source(_source, imports_and_functions)))

    pipeline.add_edge("step1", "step2")
    pipeline.add_edge("step2", "step3")

    notebook_processor.pipeline = pipeline
    notebook_processor.dependencies_detection(imports_and_functions)
    assert sorted(pipeline.get_step("step1").ins) == []
    assert sorted(pipeline.get_step("step1").outs) == []
    assert sorted(pipeline.get_step("step2").ins) == []
    assert sorted(pipeline.get_step("step2").outs) == ["foo"]
    assert sorted(pipeline.get_step("step3").ins) == ["foo"]
    assert sorted(pipeline.get_step("step3").outs) == []


def test_dependencies_detection_with_pipeline_parameters(notebook_processor, dummy_nb_config):
    """Test dependencies are detected with pipeline parameters and globals."""
    imports_and_functions = "import math"

    pipeline = Pipeline(dummy_nb_config)
    pipeline.pipeline_parameters = {"y": (5, "int")}

    _source = ["x = 5"]
    pipeline.add_step(Step(name="step1", source=_prepend_to_source(_source, imports_and_functions)))
    _source = [
        """
def foo(x):
    def bar():
        math.sqrt(x + y)
    bar()
"""
    ]
    pipeline.add_step(Step(name="step2", source=_prepend_to_source(_source, imports_and_functions)))
    _source = ["foo(5)"]
    pipeline.add_step(Step(name="step3", source=_prepend_to_source(_source, imports_and_functions)))

    pipeline.add_edge("step1", "step2")
    pipeline.add_edge("step2", "step3")

    notebook_processor.pipeline = pipeline
    notebook_processor.dependencies_detection(imports_and_functions)
    assert sorted(pipeline.get_step("step1").ins) == []
    assert sorted(pipeline.get_step("step1").outs) == []
    assert sorted(pipeline.get_step("step2").ins) == []
    assert sorted(pipeline.get_step("step2").outs) == ["foo"]
    assert pipeline.get_step("step2").parameters == {"y": (5, "int")}
    assert sorted(pipeline.get_step("step3").ins) == ["foo"]
    assert sorted(pipeline.get_step("step3").outs) == []
    assert pipeline.get_step("step3").parameters == {"y": (5, "int")}


def test_dependencies_detection_with_try_except(notebook_processor, dummy_nb_config):
    """Test dependencies are detected with functions inside try."""
    pipeline = Pipeline(dummy_nb_config)

    _source = [
        """
x = 5
y = 6
"""
    ]
    pipeline.add_step(Step(name="step1", source=_source))
    _source = [
        """
try:
    def foo():
        print(x)
    def bar():
        print(y)
except:
    pass
"""
    ]
    pipeline.add_step(Step(name="step2", source=_source))
    _source = [
        """
foo()
bar()
"""
    ]
    pipeline.add_step(Step(name="step3", source=_source))

    pipeline.add_edge("step1", "step2")
    pipeline.add_edge("step2", "step3")

    notebook_processor.pipeline = pipeline
    notebook_processor.dependencies_detection()
    assert sorted(pipeline.get_step("step1").ins) == []
    assert sorted(pipeline.get_step("step1").outs) == ["x", "y"]
    assert sorted(pipeline.get_step("step2").ins) == ["x", "y"]
    assert sorted(pipeline.get_step("step2").outs) == ["bar", "foo", "x", "y"]
    assert sorted(pipeline.get_step("step3").ins) == ["bar", "foo", "x", "y"]
    assert sorted(pipeline.get_step("step3").outs) == []


def test_dependencies_detection_recursive(notebook_processor, dummy_nb_config):
    """Test dependencies are detected even with a chain of functions calls."""
    pipeline = Pipeline(dummy_nb_config)

    _source = ["x = 5"]
    pipeline.add_step(Step(name="step1", source=_source))
    _source = [
        """
def foo():
    print(x)
def bar():
    foo()
"""
    ]
    pipeline.add_step(Step(name="step2", source=_source))
    _source = ["bar()"]
    pipeline.add_step(Step(name="step3", source=_source))

    pipeline.add_edge("step1", "step2")
    pipeline.add_edge("step2", "step3")

    notebook_processor.pipeline = pipeline
    notebook_processor.dependencies_detection()
    assert sorted(pipeline.get_step("step1").ins) == []
    assert sorted(pipeline.get_step("step1").outs) == ["x"]
    assert sorted(pipeline.get_step("step2").ins) == ["x"]
    assert sorted(pipeline.get_step("step2").outs) == ["bar", "foo", "x"]
    assert sorted(pipeline.get_step("step3").ins) == ["bar", "foo", "x"]
    assert sorted(pipeline.get_step("step3").outs) == []


def test_dependencies_detection_recursive_different_steps(notebook_processor, dummy_nb_config):
    """Test dependencies are detected even with a chain of functions calls."""
    pipeline = Pipeline(dummy_nb_config)

    _source = [
        """
x = 5
def foo():
    print(x)
"""
    ]
    pipeline.add_step(Step(name="step1", source=_source))
    _source = [
        """
def bar():
    foo()
"""
    ]
    pipeline.add_step(Step(name="step2", source=_source))
    _source = ["bar()"]
    pipeline.add_step(Step(name="step3", source=_source))

    pipeline.add_edge("step1", "step2")
    pipeline.add_edge("step2", "step3")

    notebook_processor.pipeline = pipeline
    notebook_processor.dependencies_detection()
    assert sorted(pipeline.get_step("step1").ins) == []
    assert sorted(pipeline.get_step("step1").outs) == ["foo", "x"]
    assert sorted(pipeline.get_step("step2").ins) == ["foo", "x"]
    assert sorted(pipeline.get_step("step2").outs) == ["bar", "foo", "x"]
    assert sorted(pipeline.get_step("step3").ins) == ["bar", "foo", "x"]
    assert sorted(pipeline.get_step("step3").outs) == []


def test_deps_detection_recursive_different_steps_long(notebook_processor, dummy_nb_config):
    """Test dependencies are detected even with a long chain of fns calls."""
    pipeline = Pipeline(dummy_nb_config)

    _source = [
        """
x = 5
def init():
    print(x)
"""
    ]
    pipeline.add_step(Step(name="step0", source=_source))
    _source = [
        """
def foo():
    init()
"""
    ]
    pipeline.add_step(Step(name="step1", source=_source))
    _source = [
        """
def bar():
    foo()
"""
    ]
    pipeline.add_step(Step(name="step2", source=_source))
    _source = ["bar()"]
    pipeline.add_step(Step(name="step3", source=_source))

    pipeline.add_edge("step0", "step1")
    pipeline.add_edge("step1", "step2")
    pipeline.add_edge("step2", "step3")

    notebook_processor.pipeline = pipeline
    notebook_processor.dependencies_detection()
    assert sorted(pipeline.get_step("step0").ins) == []
    assert sorted(pipeline.get_step("step0").outs) == ["init", "x"]
    assert sorted(pipeline.get_step("step1").ins) == ["init", "x"]
    assert sorted(pipeline.get_step("step1").outs) == ["foo", "init", "x"]
    assert sorted(pipeline.get_step("step2").ins) == ["foo", "init", "x"]
    assert sorted(pipeline.get_step("step2").outs) == ["bar", "foo", "init", "x"]
    assert sorted(pipeline.get_step("step3").ins) == ["bar", "foo", "init", "x"]
    assert sorted(pipeline.get_step("step3").outs) == []


def test_deps_detection_recursive_different_steps_branch(notebook_processor, dummy_nb_config):
    """Test dependencies when fns are passed from multiple branches."""
    pipeline = Pipeline(dummy_nb_config)

    _source = [
        """
x = 5
y = 6
"""
    ]
    pipeline.add_step(Step(name="step0", source=_source))
    _source = [
        """
def foo():
    print(x)
"""
    ]
    pipeline.add_step(Step(name="step_l", source=_source))
    _source = [
        """
def bar():
    print(y)
"""
    ]
    pipeline.add_step(Step(name="step_r", source=_source))
    _source = [
        """
def result():
    foo()
    bar()
"""
    ]
    pipeline.add_step(Step(name="step_m", source=_source))
    _source = ["result()"]
    pipeline.add_step(Step(name="step_f", source=_source))

    pipeline.add_edge("step0", "step_l")
    pipeline.add_edge("step0", "step_r")
    pipeline.add_edge("step_l", "step_m")
    pipeline.add_edge("step_r", "step_m")
    pipeline.add_edge("step_m", "step_f")

    notebook_processor.pipeline = pipeline
    notebook_processor.dependencies_detection()
    assert sorted(pipeline.get_step("step0").ins) == []
    assert sorted(pipeline.get_step("step0").outs) == ["x", "y"]
    assert sorted(pipeline.get_step("step_l").ins) == ["x"]
    assert sorted(pipeline.get_step("step_l").outs) == ["foo", "x"]
    assert sorted(pipeline.get_step("step_r").ins) == ["y"]
    assert sorted(pipeline.get_step("step_r").outs) == ["bar", "y"]
    assert sorted(pipeline.get_step("step_m").ins) == ["bar", "foo", "x", "y"]
    assert sorted(pipeline.get_step("step_m").outs) == ["bar", "foo", "result", "x", "y"]
    assert sorted(pipeline.get_step("step_f").ins) == ["bar", "foo", "result", "x", "y"]
    assert sorted(pipeline.get_step("step_f").outs) == []


@pytest.mark.parametrize(
    "middle_source",
    [
        "squares = [i * i for i in range(3)]",
        "total = sum(i for i in range(3))",
        "double = lambda i: i * 2",
        "i: int",
    ],
)
def test_dependencies_detection_local_scope_does_not_shadow(
    notebook_processor, dummy_nb_config, middle_source
):
    """A name that is only local in step2 is still provided by step1."""
    pipeline = Pipeline(dummy_nb_config)
    pipeline.add_step(Step(name="step1", source=["i = 5"]))
    pipeline.add_step(Step(name="step2", source=[middle_source]))
    pipeline.add_step(Step(name="step3", source=["print(i)"]))
    pipeline.add_edge("step1", "step2")
    pipeline.add_edge("step2", "step3")

    notebook_processor.pipeline = pipeline
    notebook_processor.dependencies_detection()
    assert pipeline.get_step("step1").outs == ["i"]
    assert "i" not in pipeline.get_step("step2").outs
    assert pipeline.get_step("step3").ins == ["i"]
