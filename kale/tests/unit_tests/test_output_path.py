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

"""Tests for the configurable DSL output path feature."""

import os
from unittest.mock import patch

import pytest

from kale import NotebookConfig
from kale.compiler import Compiler
from kale.pipeline import Pipeline, PipelineConfig
from kale.step import Step

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline(output_path: str = "") -> Pipeline:
    """Create a minimal one-step pipeline with the given output_path."""
    config = PipelineConfig(
        pipeline_name="test-pipeline",
        experiment_name="test-experiment",
        output_path=output_path,
    )
    pipeline = Pipeline(config)
    step = Step(name="step_one", source=["x = 1"])
    pipeline.add_step(step)
    return pipeline


def _make_compiler(pipeline: Pipeline) -> Compiler:
    """Create a Compiler wrapping the given pipeline."""
    compiler = Compiler(pipeline, imports_and_functions="")
    compiler.dsl_source = "# generated DSL"
    return compiler


# ---------------------------------------------------------------------------
# PipelineConfig field tests
# ---------------------------------------------------------------------------


class TestOutputPathField:
    def test_default_is_empty_string(self, dummy_nb_config):
        config = NotebookConfig(**dummy_nb_config)
        assert config.output_path == ""

    def test_can_be_set_via_kwargs(self, dummy_nb_config):
        config = NotebookConfig(**{**dummy_nb_config, "output_path": "my_output"})
        assert config.output_path == "my_output"

    def test_survives_to_dict(self, dummy_nb_config):
        config = NotebookConfig(**{**dummy_nb_config, "output_path": "dsl_out"})
        assert config.to_dict()["output_path"] == "dsl_out"

    def test_empty_string_survives_to_dict(self, dummy_nb_config):
        config = NotebookConfig(**dummy_nb_config)
        assert config.to_dict()["output_path"] == ""


# ---------------------------------------------------------------------------
# Compiler._save_compiled_code tests
# ---------------------------------------------------------------------------


class TestSaveCompiledCode:
    def test_default_saves_to_kale_dir(self, tmp_path):
        """When output_path is empty the DSL goes into .kale/ under CWD."""
        pipeline = _make_pipeline(output_path="")
        compiler = _make_compiler(pipeline)

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = compiler._save_compiled_code()

        expected_dir = tmp_path / ".kale"
        assert expected_dir.is_dir()
        assert result == str(expected_dir / "test-pipeline.kale.py")

    def test_custom_relative_path_is_used(self, tmp_path):
        """When output_path is set the DSL is written to that relative path."""
        pipeline = _make_pipeline(output_path="my_dsl_output")
        compiler = _make_compiler(pipeline)

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = compiler._save_compiled_code()

        expected_dir = tmp_path / "my_dsl_output"
        assert expected_dir.is_dir()
        assert result == str(expected_dir / "test-pipeline.kale.py")

    def test_custom_nested_relative_path_is_used(self, tmp_path):
        """Nested relative paths like 'a/b/c' are created as needed."""
        pipeline = _make_pipeline(output_path="compiled/pipelines")
        compiler = _make_compiler(pipeline)

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = compiler._save_compiled_code()

        expected_dir = tmp_path / "compiled" / "pipelines"
        assert expected_dir.is_dir()
        assert result == str(expected_dir / "test-pipeline.kale.py")

    def test_absolute_path_argument_takes_precedence(self, tmp_path):
        """An explicit path= argument overrides both config and default."""
        pipeline = _make_pipeline(output_path="should_be_ignored")
        compiler = _make_compiler(pipeline)
        explicit_dir = str(tmp_path / "explicit")

        result = compiler._save_compiled_code(path=explicit_dir)

        assert os.path.isdir(explicit_dir)
        assert result == os.path.join(explicit_dir, "test-pipeline.kale.py")

    def test_dsl_content_is_written(self, tmp_path):
        """The generated DSL source is actually written to disk."""
        pipeline = _make_pipeline(output_path="out")
        compiler = _make_compiler(pipeline)
        compiler.dsl_source = "# my pipeline code"

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = compiler._save_compiled_code()

        assert open(result).read() == "# my pipeline code"

    def test_dsl_script_path_is_set(self, tmp_path):
        """After saving, compiler.dsl_script_path points to the written file."""
        pipeline = _make_pipeline(output_path="")
        compiler = _make_compiler(pipeline)

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = compiler._save_compiled_code()

        assert compiler.dsl_script_path == result


# ---------------------------------------------------------------------------
# Invalid output_path validation tests
# ---------------------------------------------------------------------------


class TestOutputPathValidation:
    @pytest.mark.parametrize(
        "output_path", ["../project-other/output", "nested/../../project-other"]
    )
    def test_sibling_with_shared_prefix_is_rejected(self, tmp_path, monkeypatch, output_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        with pytest.raises(ValueError, match="not a valid output directory"):
            PipelineConfig(
                pipeline_name="test-pipeline",
                experiment_name="test-experiment",
                output_path=output_path,
            )

    def test_symlink_to_sibling_with_shared_prefix_is_rejected(self, tmp_path, monkeypatch):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        outside_dir = tmp_path / "project-other"
        outside_dir.mkdir()
        (project_dir / "output").symlink_to(outside_dir, target_is_directory=True)
        monkeypatch.chdir(project_dir)

        with pytest.raises(ValueError, match="not a valid output directory"):
            PipelineConfig(
                pipeline_name="test-pipeline",
                experiment_name="test-experiment",
                output_path="output/pipelines",
            )

    @pytest.mark.parametrize("output_path", [".", "nested/../output", "project-other/output"])
    def test_contained_paths_are_accepted(self, tmp_path, monkeypatch, output_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        config = PipelineConfig(
            pipeline_name="test-pipeline",
            experiment_name="test-experiment",
            output_path=output_path,
        )
        assert config.output_path == output_path

    def test_absolute_path_is_rejected(self):
        """Absolute paths like '/tmp/output' should be rejected."""
        with pytest.raises(ValueError, match="not a valid output directory"):
            PipelineConfig(
                pipeline_name="test-pipeline",
                experiment_name="test-experiment",
                output_path="/tmp/output",
            )

    def test_dotdot_path_is_rejected(self):
        """Paths containing '..' should be rejected."""
        with pytest.raises(ValueError, match="not a valid output directory"):
            PipelineConfig(
                pipeline_name="test-pipeline",
                experiment_name="test-experiment",
                output_path="../outside",
            )

    def test_dotdot_nested_path_is_rejected(self):
        """Nested paths with '..' like 'foo/../../bar' should be rejected."""
        with pytest.raises(ValueError, match="not a valid output directory"):
            PipelineConfig(
                pipeline_name="test-pipeline",
                experiment_name="test-experiment",
                output_path="foo/../../bar",
            )

    def test_valid_relative_path_is_accepted(self):
        """Normal relative paths like 'pipelines/output' should work fine."""
        config = PipelineConfig(
            pipeline_name="test-pipeline",
            experiment_name="test-experiment",
            output_path="pipelines/output",
        )
        assert config.output_path == "pipelines/output"

    def test_empty_string_is_accepted(self):
        """Empty string (default) should pass validation."""
        config = PipelineConfig(
            pipeline_name="test-pipeline",
            experiment_name="test-experiment",
            output_path="",
        )
        assert config.output_path == ""
