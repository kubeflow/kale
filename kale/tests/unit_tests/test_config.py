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

from kale import NotebookConfig
from kale.pipeline import VolumeConfig


@pytest.mark.parametrize(
    "args",
    [
        (None, []),
        ("/users", [{"name": "test", "type": "pvc", "mount_point": "/root"}]),
        ("/user/kale/test", [{"name": "test", "type": "pvc", "mount_point": "/user/kale"}]),
        ("/user/kale/", [{"name": "test", "type": "pvc", "mount_point": "/user/kale/test"}]),
    ],
)
def test_get_marshal_data(dummy_nb_config, args):
    """Test that marshal_path is always the default /tmp/marshal regardless of volumes."""
    config = NotebookConfig(
        **{
            **dummy_nb_config,
            "abs_working_dir": args[0],
            "volumes": args[1],
            "notebook_path": "/user/kale/test/mynb.ipynb",
        }
    )
    assert config.marshal_path == "/tmp/marshal"


@pytest.mark.parametrize(
    "volume_kwargs,expected_expose",
    [
        ({"name": "my-data", "type": "pvc", "mount_point": "/data"}, False),
        (
            {"name": "my-data", "type": "pvc", "mount_point": "/data", "expose_as_env_var": True},
            True,
        ),
        (
            {"name": "my-data", "type": "pvc", "mount_point": "/data", "expose_as_env_var": False},
            False,
        ),
    ],
)
def test_volume_config_expose_as_env_var(volume_kwargs, expected_expose):
    """VolumeConfig.expose_as_env_var defaults to False and round-trips through to_dict()."""
    vol = VolumeConfig(**volume_kwargs)
    assert vol.expose_as_env_var is expected_expose
    d = vol.to_dict()
    assert d.get("expose_as_env_var") is expected_expose


def test_volume_expose_as_env_var_propagates_through_pipeline_config(dummy_nb_config):
    """expose_as_env_var survives the full NotebookConfig → to_dict() path."""
    config = NotebookConfig(
        **{
            **dummy_nb_config,
            "notebook_path": "/user/kale/test/mynb.ipynb",
            "volumes": [
                {
                    "name": "raw-data",
                    "type": "pvc",
                    "mount_point": "/data",
                    "expose_as_env_var": True,
                },
                {"name": "model-store", "type": "pvc", "mount_point": "/models"},
            ],
        }
    )
    vols = config.to_dict()["volumes"]
    assert vols[0]["expose_as_env_var"] is True
    assert vols[1]["expose_as_env_var"] is False


@pytest.mark.parametrize(
    "configs",
    [
        (
            {
                "katib_metadata": {
                    "parameters": ["a"],
                    "algorithm": {"dummy": "test"},
                    "objective": {"dummy": "test"},
                }
            }
        )
    ],
)
def test_nested_configs(dummy_nb_config, configs):
    """Test that nested Configs are parsed properly."""
    config = NotebookConfig(**{**dummy_nb_config, **configs})
    # add defaults
    res = {
        **configs["katib_metadata"],
        "maxFailedTrialCount": 3,
        "maxTrialCount": 12,
        "parallelTrialCount": 3,
    }
    assert config.katib_metadata.to_dict() == res
