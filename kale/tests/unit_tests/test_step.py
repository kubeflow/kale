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
"""Tests for the pipeline node types (kale.step)."""

import pytest

from kale.pipeline import Pipeline, PipelineConfig
from kale.step import Step, SubPipeline


def _pipeline(name="child"):
    return Pipeline(PipelineConfig(pipeline_name=name, experiment_name="test"))


def _sub(name="trainer", source=None, **kwargs):
    return SubPipeline(
        pipeline=_pipeline(),
        notebook_path="./trainer.ipynb",
        source=source or ["model = fit(dataset)"],
        name=name,
        **kwargs,
    )


def test_subpipeline_carries_the_step_interface():
    """A SubPipeline exposes the same name/ins/outs/config a Step does, so both
    can be handled by one scanner and one template."""
    sub = _sub(ins=["dataset"], outs=["model"])

    assert sub.name == "trainer"
    assert sub.ins == ["dataset"]
    assert sub.outs == ["model"]
    assert sub.config.name == "trainer"


def test_subpipeline_is_a_pipeline_node():
    """A SubPipeline sits in the graph next to plain Steps, and is ordered with
    them by the same topological sort."""
    pipeline = _pipeline("root")
    prepare = Step(source=["dataset = load()"], name="prepare")
    trainer = _sub()
    report = Step(source=["print(model)"], name="report")
    for node in (prepare, trainer, report):
        pipeline.add_step(node)
    pipeline.add_edge("prepare", "trainer")
    pipeline.add_edge("trainer", "report")

    assert pipeline.steps_names == ["prepare", "trainer", "report"]
    assert isinstance(pipeline.get_step("trainer"), SubPipeline)


def test_subpipeline_source_is_scannable_like_a_step():
    """Boundary detection reads `source` the same way for both node types, which
    is what lets a variable cross a notebook boundary like a step boundary."""
    from kale.common import astutils, flakeutils

    sub = _sub(source=["model = fit(dataset)"])
    code = "\n".join(sub.source)

    assert "dataset" in flakeutils.pyflakes_report(code=code)
    assert "model" in astutils.get_marshal_candidates(code)


def test_subpipeline_keeps_its_own_config():
    """Per-notebook configuration lives on the node, so it cannot be dropped
    when the pipeline is emitted."""
    sub = _sub(base_image="kale-runtime:2.1.0", enable_caching=False)

    assert sub.config.base_image == "kale-runtime:2.1.0"
    assert sub.config.enable_caching is False


def test_subpipeline_display_name_defaults_to_a_kfp_safe_name():
    """The node name drives generated identifiers; the display name is what the
    KFP UI shows."""
    assert _sub(name="kale_notebook_trainer").display_name == "kale-notebook-trainer"
    assert _sub(name="trainer", display_name="trainer-nb").display_name == "trainer-nb"


def test_subpipeline_refuses_merged_code():
    """A `notebook:` reference cell holds no code, so nothing can merge into it."""
    with pytest.raises(RuntimeError, match="references a notebook"):
        _sub().merge_code("x = 1")


def test_subpipeline_runs_its_child_steps(monkeypatch):
    """Running a SubPipeline locally runs the referenced notebook's steps."""
    sub = _sub()
    ran = []
    for name in ("fit", "package"):
        step = Step(source=[f"{name}()"], name=name)
        monkeypatch.setattr(step, "run", lambda _params, n=name: ran.append(n))
        sub.pipeline.add_step(step)
    sub.pipeline.add_edge("fit", "package")

    sub.run({})

    assert ran == ["fit", "package"]
