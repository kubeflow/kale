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
"""Tests for the flags of the `kale` command line interface."""

import sys
from unittest import mock

import nbformat as nbf

from kale import cli


def _write_nb(path):
    """Write a single-step notebook with empty Kale metadata."""
    nb = nbf.v4.new_notebook()
    nb.metadata["kubeflow_notebook"] = {"volumes": []}
    cell = nbf.v4.new_code_cell(source="x = 1")
    cell.metadata["tags"] = ["step:one"]
    nb.cells.append(cell)
    nbf.write(nb, str(path))
    return path


def test_docker_image_flag_sets_base_image(tmp_path, monkeypatch):
    """`--docker_image` sets the base image of the generated components.

    Regression test: the flag was passed on as a `docker_image` metadata
    override, a field the config does not have, so the CLI failed with a
    RuntimeError.
    """
    nb = _write_nb(tmp_path / "nb.ipynb")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["kale", "--nb", str(nb), "--docker_image", "python:3.12"])

    # Building the KFP package from the generated DSL is out of scope here.
    with mock.patch.object(cli.kfputils, "compile_pipeline"):
        cli.main()

    (dsl_script,) = (tmp_path / ".kale").glob("*.kale.py")
    assert "base_image='python:3.12'" in dsl_script.read_text()
