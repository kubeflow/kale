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

import pytest
from testfixtures import compare

from kale.common import astutils as kale_ast

_numpy_snippet = """
import os
import numpy as np
a = np.random.random((10, 10))
b = a.sum()
print(b)
"""

_numpy2_snippet = """
import os
import numpy as np
b = a.sum()
print(b)
"""

_foos_snippet = """
def _test(a):
    pass

def _test2(b, *args, **kwargs):
    var = b
"""

_class_snippet = """
class test:
    def __init__(self, a):
        self.a = a

    def foo(self, b):
        self.a = b
"""

_async_snippet = """
async def _test(a):
    local_var = a

async def _test2(b, *args, **kwargs):
    var = b
"""

_ctx_mngr_snippet = """
with my_context(param) as ctx:
    res = ctx.use()
"""

_wrong_code_snippet = """
def fun()
    pass
"""


@pytest.mark.parametrize(
    "code,target",
    [
        ("", []),
        (_numpy_snippet, ["a", "b", "np", "os", "print"]),
        (_numpy2_snippet, ["a", "b", "np", "os", "print"]),
        (_foos_snippet, ["_test", "_test2"]),
        (_class_snippet, ["test"]),
        (_ctx_mngr_snippet, ["my_context", "param", "res", "ctx"]),
        # async functions are treated like regular functions: the function
        # name is a candidate, their local variables must not leak out.
        (_async_snippet, ["_test", "_test2"]),
    ],
)
def test_get_marshal_candidates(code, target):
    """Tests get_marshal_candidates function."""
    res = kale_ast.get_marshal_candidates(code)
    assert sorted(res) == sorted(target)


def test_get_marshal_candidates_exc():
    """Tests exception when passing a wrong code snippet."""
    with pytest.raises(SyntaxError):
        kale_ast.get_marshal_candidates(_wrong_code_snippet)


@pytest.mark.parametrize(
    "code,target",
    [
        ("()", []),
        ("[]", []),
        ("(a,)", ["a"]),
        ("[a,]", ["a"]),
        ("(a,(b,))", ["a", "b"]),
        ("[a,[b,]]", ["a", "b"]),
    ],
)
def test_get_list_tuple_names(code, target):
    """Test list_tuple_names function."""
    tree = ast.parse(code)
    res = kale_ast.get_list_tuple_names(tree.body[0].value)
    assert sorted(res) == sorted(target)


@pytest.mark.parametrize(
    "code,target",
    [
        ("", []),
        (_foos_snippet, ["_test", "_test2"]),
        (_class_snippet, ["__init__", "foo", "test"]),
        (_async_snippet, ["_test", "_test2"]),
    ],
)
def test_get_function_and_class_names(code, target):
    """Test get_function_and_class_names function."""
    res = kale_ast.get_function_and_class_names(code)
    assert sorted(res) == sorted(target)


@pytest.mark.parametrize(
    "code,target",
    [
        ("", {}),
        ('a = "a"', {"a": (str.__name__, "a")}),
        ("a = 3", {"a": (int.__name__, 3)}),
        ("a = 2.", {"a": (float.__name__, 2.0)}),
        ("a = True", {"a": (bool.__name__, True)}),
    ],
)
def test_parse_assignments_expressions(code, target):
    """Test parse_assignments_expressions function."""
    res = kale_ast.parse_assignments_expressions(code)
    compare(res, target)


@pytest.mark.parametrize(
    "code",
    [
        "a = None",
        "a + 1",
        "a, b = 3",
        "a = b = 3",
        "a = [2]",
        "a = b",
    ],
)
def test_parse_assignments_expressions_exc(code):
    """Test parse_assignments_expressions function."""
    with pytest.raises(ValueError):
        kale_ast.parse_assignments_expressions(code)


@pytest.mark.parametrize(
    "code, target",
    [
        ("", {}),
        ("   ", {}),
        ("print(a)", {"a": "a"}),
        ("print(a)\nprint(var)\nprint(test_var)", {"a": "a", "var": "var", "test-var": "test_var"}),
    ],
)
def test_parse_metrics_print_statements(code, target):
    """Tests parse_metrics_print_statements function."""
    res = kale_ast.parse_metrics_print_statements(code)
    assert res == target


@pytest.mark.parametrize(
    "code", ["print(foo())", "def", "variable", "print(var)\nname", "_variable"]
)
def test_parse_metrics_print_statements_exc(code):
    """Tests a exception cases for parse_metrics_print_statements function."""
    with pytest.raises(ValueError):
        kale_ast.parse_metrics_print_statements(code)


def test_parse_functions():
    """Test that the body of the function is retrieved correctly."""
    code = """
x = 5
def foo():
    print('hello')
    print(x)
    """

    target = {"foo": "def foo():\n    print('hello')\n    print(x)\n"}
    assert kale_ast.parse_functions(code) == target


def test_parse_functions_async():
    """async functions must be parsed just like regular functions."""
    code = """
x = 5
async def foo():
    print('hello')
    print(x)
    """

    target = {"foo": "async def foo():\n    print('hello')\n    print(x)\n"}
    assert kale_ast.parse_functions(code) == target


def test_get_calls():
    """Test that just function calls are detected."""
    code = """
a.obj()
foo()
        """
    assert kale_ast.get_function_calls(code) == {"foo"}

    code = """
x = 5
def foo():
    print(x)
        """
    assert kale_ast.get_function_calls(code) == {"print"}


def test_get_function_source():
    """Test that the function source is properly retrieved."""

    def foo():
        a = 1  # noqa: F841
        b = 2  # noqa: F841

    target = "a = 1\nb = 2\n"
    assert kale_ast.get_function_source(foo) == target


def test_get_function_source_with_signature():
    """Test that the function source is properly retrieved with signature."""

    def foo():
        a = 1  # noqa: F841
        b = 2  # noqa: F841

    target = "def foo():\n    a = 1\n    b = 2\n"
    assert kale_ast.get_function_source(foo, strip_signature=False) == target


def test_get_function_source_with_signature_and_decorator():
    """Test that the function source is properly retrieved with signature."""

    def foodec(**kwargs):
        def _(fn):
            return fn

        return _

    @foodec(a=1, b=2, c=3, d=4)
    def foo():
        a = 1  # noqa: F841
        b = 2  # noqa: F841

    target = "def foo():\n    a = 1\n    b = 2\n"
    assert kale_ast.get_function_source(foo, strip_signature=False) == target


def test_link_fns_to_inputs_vars():
    """Test the fn produces a correct map between fn calls and input args."""
    source = "res = foo(a, b, c)\nres2 = bar(d, c)\nfoo2(f)\n"

    target = {"foo": ["a", "b", "c"], "bar": ["d", "c"], "foo2": ["f"]}

    assert kale_ast.link_fns_to_inputs_vars(source) == target


def test_link_fns_to_return_vars():
    """Test the fn produces a correct map between fn calls and return vars."""
    source = "res = foo(a, b, c)\nres2 = bar(d, c)\nfoo2(f)\n"

    target = {"foo": ["res"], "bar": ["res2"]}

    assert kale_ast.link_fns_to_return_vars(source) == target


def test_parse_assignments_expressions_exc_none():
    """Test parse_assignments_expressions function raises correct error for None."""
    with pytest.raises(ValueError) as exec:
        kale_ast.parse_assignments_expressions("a = None")
    assert "`None` value None is not supported in pipeline parameters" in str(exec.value)


@pytest.mark.parametrize(
    "code,target",
    [
        ("chroma_db = build_db()\nchroma_db", "chroma_db"),
        ("x = 1\ny = 2\ny", "y"),
        ("result", "result"),
        ("data = load()\n# trailing comment\ndata  ", "data"),
        ("def f():\n    return 1\nf", "f"),
        ("model = train()\nprint(model)", None),  # print, not a bare name
        ("df = load()\ndf.head()", None),  # method call
        ("obj = get()\nobj.attr", None),  # attribute access
        ("a = 1\nb = a + 1", None),  # assignment last
        ("", None),
        ("   \n   ", None),
        ("x = (", None),  # syntax error -> None
    ],
)
def test_get_trailing_variable(code, target):
    assert kale_ast.get_trailing_variable(code) == target
