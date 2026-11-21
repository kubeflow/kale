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

import nbformat
import pytest

from kale import NotebookConfig, Pipeline, Step
from kale.processors.nbprocessor import NotebookProcessor


def test_merge_code(dummy_nb_config):
    """Test the merge code functionality."""
    pipeline = Pipeline(NotebookConfig(**dummy_nb_config))
    pipeline.add_step(Step(name="test", source=["test1"]))
    pipeline.get_step("test").merge_code("test2")

    assert pipeline.get_step("test").source == ["test1", "test2"]


_EMPTY_TAG = {"step_names": [], "prev_steps": []}


@pytest.mark.parametrize(
    "metadata,target",
    [
        ({}, _EMPTY_TAG),
        ({"tags": []}, _EMPTY_TAG),
        ({"other_field": None}, _EMPTY_TAG),
        # test special tags
        ({"tags": ["imports"]}, {"step_names": ["imports"], "prev_steps": []}),
        (
            {"tags": ["pipeline-parameters"]},
            {"step_names": ["pipeline-parameters"], "prev_steps": []},
        ),
        ({"tags": ["functions"]}, {"step_names": ["functions"], "prev_steps": []}),
        # test skip tag
        ({"tags": ["skip"]}, {"step_names": ["skip"], "prev_steps": []}),
        ({"tags": ["skip", "step:other"]}, {"step_names": ["skip"], "prev_steps": []}),
        # test that prev tag is ignored when having a special tag
        ({"tags": ["imports", "prev:step1"]}, {"step_names": ["imports"], "prev_steps": []}),
        ({"tags": ["functions", "prev:step1"]}, {"step_names": ["functions"], "prev_steps": []}),
        (
            {"tags": ["pipeline-parameters", "prev:step1"]},
            {"step_names": ["pipeline-parameters"], "prev_steps": []},
        ),
        # when specifying multiple steps, only the special step tag name
        # is returned
        ({"tags": ["imports", "step:step1"]}, {"step_names": ["imports"], "prev_steps": []}),
        ({"tags": ["functions", "step:step1"]}, {"step_names": ["functions"], "prev_steps": []}),
        (
            {"tags": ["pipeline-parameters", "step:step1"]},
            {"step_names": ["pipeline-parameters"], "prev_steps": []},
        ),
    ],
)
def test_parse_metadata_success(notebook_processor, metadata, target):
    """Test parse_metadata function."""
    notebook_processor.parse_cell_metadata(metadata)


@pytest.mark.parametrize(
    "metadata",
    [
        ({"tags": ["random_value"]}),
        ({"tags": [0]}),
        ({"tags": ["prev:step2"]}),
        # secret tags require a step name
        ({"tags": ["secret:db-credentials:password:DB_PASSWORD"]}),
        # malformed secret tags (wrong number of parts / invalid names)
        ({"tags": ["step:test", "secret:db-credentials:password"]}),
        ({"tags": ["step:test", "secret:DB-creds:password:DB_PASSWORD"]}),
        ({"tags": ["step:test", "secret:db-credentials:password:1_INVALID"]}),
    ],
)
def test_parse_metadata_exc(notebook_processor, metadata):
    """Test parse_metadata exception cases."""
    with pytest.raises(ValueError):
        notebook_processor.parse_cell_metadata(metadata)


def test_parse_metadata_secret_tag(notebook_processor):
    """Test that a well-formed secret tag is parsed into the secrets dict."""
    tags = notebook_processor.parse_cell_metadata(
        {"tags": ["step:test", "secret:db-credentials:password:DB_PASSWORD"]}
    )

    assert tags["secrets"] == {
        "DB_PASSWORD": {"secret_name": "db-credentials", "secret_key": "password"}
    }


def test_parse_metadata_dotted_secret_name(notebook_processor):
    """Test that a Secret name with dots (a valid DNS subdomain) is accepted."""
    tags = notebook_processor.parse_cell_metadata(
        {"tags": ["step:test", "secret:my.db-credentials:password:DB_PASSWORD"]}
    )

    assert tags["secrets"] == {
        "DB_PASSWORD": {"secret_name": "my.db-credentials", "secret_key": "password"}
    }


def test_parse_metadata_multiple_secret_tags(notebook_processor):
    """Test that multiple secret tags on the same cell are all captured."""
    tags = notebook_processor.parse_cell_metadata(
        {
            "tags": [
                "step:test",
                "secret:db-credentials:password:DB_PASSWORD",
                "secret:api-credentials:token:API_TOKEN",
            ]
        }
    )

    assert tags["secrets"] == {
        "DB_PASSWORD": {"secret_name": "db-credentials", "secret_key": "password"},
        "API_TOKEN": {"secret_name": "api-credentials", "secret_key": "token"},
    }


def test_get_pipeline_parameters_source_simple(notebook_processor):
    """Test that the function gets the correct pipeline parameters source."""
    notebook = nbformat.v4.new_notebook()
    cells = [
        ("0", {}),
        ("0", {"tags": []}),
        ("1", {"tags": ["pipeline-parameters"]}),
        ("1", {}),
    ]
    notebook.cells = [nbformat.v4.new_code_cell(source=s, metadata=m) for (s, m) in cells]
    notebook_processor.notebook = notebook
    assert notebook_processor.get_pipeline_parameters_source() == "1\n1"


def test_get_pipeline_parameters_source_with_step(notebook_processor):
    """Test that the function gets the correct pipeline parameters source."""
    notebook = nbformat.v4.new_notebook()
    cells = [
        ("1", {"tags": ["pipeline-parameters"]}),
        ("0", {"tags": ["step:test"]}),
        ("1", {"tags": ["pipeline-parameters"]}),
    ]
    notebook.cells = [nbformat.v4.new_code_cell(source=s, metadata=m) for (s, m) in cells]
    notebook_processor.notebook = notebook
    assert notebook_processor.get_pipeline_parameters_source() == "1\n1"


def test_get_pipeline_parameters_source_skip(notebook_processor):
    """Test that the function gets the correct pipeline parameters source."""
    notebook = nbformat.v4.new_notebook()
    cells = [
        ("1", {"tags": ["pipeline-parameters"]}),
        ("0", {"tags": ["skip"]}),
        ("1", {"tags": ["pipeline-parameters"]}),
        ("1", {"tags": []}),
    ]
    notebook.cells = [nbformat.v4.new_code_cell(source=s, metadata=m) for (s, m) in cells]
    notebook_processor.notebook = notebook
    assert notebook_processor.get_pipeline_parameters_source() == "1\n1\n1"


def test_get_pipeline_parameters_source_followed_reserved(notebook_processor):
    """Test that the function gets the correct pipeline parameters source."""
    notebook = nbformat.v4.new_notebook()
    cells = [
        ("1", {"tags": ["pipeline-parameters"]}),
        ("0", {"tags": ["imports"]}),
        ("1", {"tags": ["pipeline-parameters"]}),
        ("1", {"tags": []}),
    ]
    notebook.cells = [nbformat.v4.new_code_cell(source=s, metadata=m) for (s, m) in cells]
    notebook_processor.notebook = notebook
    assert notebook_processor.get_pipeline_parameters_source() == "1\n1\n1"


def test_assign_metrics_only_marks_steps_with_assigned_metrics():
    """Regression test for #787: metrics flag must only be set on steps that
    actually have a metric variable, not on every leaf node traversed."""
    pipeline = Pipeline("test")
    step_a = Step(source=["accuracy = 0.95"], name="step_a")
    step_b = Step(source=["x = 1"], name="step_b")
    pipeline.add_step(step_a)
    pipeline.add_step(step_b)

    proc = NotebookProcessor.__new__(NotebookProcessor)
    proc.pipeline = pipeline
    proc.assign_metrics({"accuracy": "accuracy"})

    assert step_a.metrics is True, "step with metric variable should have metrics=True"
    assert step_b.metrics is False, "step without metric variable should not get metrics=True"


def test_get_pipeline_metrics_source_raises(notebook_processor):
    """Test exception when pipeline metrics isn't at the end of notebook."""
    notebook = nbformat.v4.new_notebook()
    cells = [
        ("1", {"tags": ["pipeline-metrics"]}),
        ("0", {"tags": ["imports"]}),
    ]
    notebook.cells = [nbformat.v4.new_code_cell(source=s, metadata=m) for (s, m) in cells]
    with pytest.raises(
        ValueError,
        match=r"Tag pipeline-metrics tag must be"
        r" placed on a cell at the end of"
        r" the Notebook\..*",
    ):
        notebook_processor.notebook = notebook
        notebook_processor.get_pipeline_metrics_source()


@pytest.mark.parametrize(
    "metadata,expected_report_value",
    [
        ({"tags": ["step:test", "report:enabled"]}, True),
        ({"tags": ["step:test", "report:disabled"]}, False),
        ({"tags": ["step:test"]}, None),  # No report tag means None (use default)
    ],
)
def test_parse_report_tag(notebook_processor, metadata, expected_report_value):
    """Test that report:enabled and report:disabled tags are parsed correctly."""
    result = notebook_processor.parse_cell_metadata(metadata)
    assert result.get("generate_html_report") == expected_report_value


def test_report_tag_requires_step(notebook_processor):
    """Test that report tag raises an error when used without a step tag."""
    metadata = {"tags": ["report:disabled"]}
    with pytest.raises(
        ValueError,
        match=r"A cell can not provide HTML report control in a"
        r" cell that does not declare a step name\.",
    ):
        notebook_processor.parse_cell_metadata(metadata)


def test_compiler_includes_html_report_by_default():
    """Test that HTML report output is included when generate_html_report is not disabled."""
    from kale.compiler import Compiler
    from kale.pipeline import Pipeline, PipelineConfig

    config = PipelineConfig(pipeline_name="test", experiment_name="test")
    pipeline = Pipeline(config)
    step = Step(name="my_step", source=["x = 1"])
    pipeline.add_step(step)

    compiler = Compiler(pipeline, imports_and_functions="")
    component_code = compiler.generate_lightweight_component(step)

    assert "my_step_html_report: Output[HTML]" in component_code
    assert "_kale_html_artifact = _kale_run_code(_kale_blocks)" in component_code


def test_compiler_excludes_html_report_when_disabled():
    """Test that HTML report output is excluded when generate_html_report=False."""
    from kale.compiler import Compiler
    from kale.pipeline import Pipeline, PipelineConfig

    config = PipelineConfig(pipeline_name="test", experiment_name="test")
    pipeline = Pipeline(config)
    step = Step(name="my_step", source=["x = 1"], generate_html_report=False)
    pipeline.add_step(step)

    compiler = Compiler(pipeline, imports_and_functions="")
    component_code = compiler.generate_lightweight_component(step)

    assert "my_step_html_report: Output[HTML]" not in component_code
    assert "_kale_html_artifact = _kale_run_code(_kale_blocks)" not in component_code
    # Should still call _kale_run_code, just without capturing the artifact
    assert "_kale_run_code(_kale_blocks)" in component_code


def test_compiler_includes_html_report_when_explicitly_enabled():
    """Test that HTML report output is included when generate_html_report=True."""
    from kale.compiler import Compiler
    from kale.pipeline import Pipeline, PipelineConfig

    config = PipelineConfig(pipeline_name="test", experiment_name="test")
    pipeline = Pipeline(config)
    step = Step(name="my_step", source=["x = 1"], generate_html_report=True)
    pipeline.add_step(step)

    compiler = Compiler(pipeline, imports_and_functions="")
    component_code = compiler.generate_lightweight_component(step)

    assert "my_step_html_report: Output[HTML]" in component_code
    assert "_kale_html_artifact = _kale_run_code(_kale_blocks)" in component_code
