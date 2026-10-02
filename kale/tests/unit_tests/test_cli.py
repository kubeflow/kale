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
"""Tests for how the CLI resolves notebook metadata against its own arguments."""

import nbformat as nbf
import pytest

from kale.cli import DEFAULT_EXPERIMENT_NAME, DEFAULT_PIPELINE_NAME
from kale.processors import NotebookProcessor


def _write_nb(path, metadata):
    """Write a single-step notebook whose Kale metadata is `metadata`."""
    nb = nbf.v4.new_notebook()
    nb.metadata["kubeflow_notebook"] = {"volumes": [], **metadata}
    cell = nbf.v4.new_code_cell(source="x = 1")
    cell.metadata["tags"] = ["step:one"]
    nb.cells.append(cell)
    nbf.write(nb, str(path))
    return path


def _cli_config(path, overrides=None):
    """Build the config the way `kale --nb` does.

    The CLI passes its own defaults as kwargs (resolved *below* the notebook's
    metadata) and only explicitly-given arguments as metadata overrides
    (resolved *above* it).
    """
    processor = NotebookProcessor(
        str(path),
        overrides or {},
        pipeline_name=DEFAULT_PIPELINE_NAME,
        experiment_name=DEFAULT_EXPERIMENT_NAME,
    )
    return processor.config


@pytest.mark.parametrize("field", ["pipeline_name", "experiment_name"])
def test_notebook_metadata_is_not_clobbered_by_cli_defaults(tmp_path, field):
    """A name set in the notebook survives a CLI run that does not pass one.

    Regression test: both arguments used to carry an argparse default, so they
    were always present in the overrides dict and always won over the notebook.
    Two notebooks compiled in one directory therefore shared a pipeline name and
    silently overwrote each other's generated modules.
    """
    nb = _write_nb(tmp_path / "nb.ipynb", {field: "from-metadata"})

    assert getattr(_cli_config(nb), field) == "from-metadata"


@pytest.mark.parametrize(
    "field,default",
    [("pipeline_name", DEFAULT_PIPELINE_NAME), ("experiment_name", DEFAULT_EXPERIMENT_NAME)],
)
def test_cli_default_applies_when_notebook_names_neither(tmp_path, field, default):
    """With nothing in the notebook, the CLI default is still the fallback."""
    nb = _write_nb(tmp_path / "nb.ipynb", {})

    assert getattr(_cli_config(nb), field) == default


@pytest.mark.parametrize("field", ["pipeline_name", "experiment_name"])
def test_explicit_cli_argument_still_wins(tmp_path, field):
    """An explicitly passed argument keeps precedence over the notebook."""
    nb = _write_nb(tmp_path / "nb.ipynb", {field: "from-metadata"})

    config = _cli_config(nb, {field: "from-cli"})

    assert getattr(config, field) == "from-cli"


def test_two_notebooks_keep_distinct_pipeline_names(tmp_path):
    """The names two notebooks are compiled under stay distinct.

    This is what keeps their generated sub-pipeline modules from colliding:
    `_module_name` is keyed on the root pipeline name.
    """
    first = _write_nb(tmp_path / "first.ipynb", {"pipeline_name": "first-pipeline"})
    second = _write_nb(tmp_path / "second.ipynb", {"pipeline_name": "second-pipeline"})

    assert _cli_config(first).pipeline_name != _cli_config(second).pipeline_name
