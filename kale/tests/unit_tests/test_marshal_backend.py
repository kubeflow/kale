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
"""Tests for missing-library fallback in marshalling backends."""

from pathlib import Path

import pytest

from kale.marshal import backend


class MissingLibraryBackend(backend.MarshalBackend):
    file_type = "custom"
    obj_type_regex = r"dict"

    def save(self, obj, path):
        raise ImportError("optional serializer unavailable")

    def load(self, file_path):
        raise ImportError("optional serializer unavailable")


@pytest.fixture
def marshal_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "artifacts"
    data_dir.mkdir()
    working_dir = tmp_path / "working"
    working_dir.mkdir()
    monkeypatch.chdir(working_dir)
    monkeypatch.setattr(backend, "__DATA_DIR", str(data_dir))
    return data_dir


def test_save_fallback_writes_to_returned_path(marshal_dir):
    serializer = MissingLibraryBackend()
    value = {"numbers": [1, 2, 3]}

    saved_path = serializer.wrapped_save(value, "value")

    assert saved_path == str(marshal_dir / "value.custom")
    assert Path(saved_path).is_file()
    assert not Path("value").exists()
    assert serializer.wrapped_load("value") == value


def test_dispatcher_can_find_and_load_fallback_artifact(marshal_dir):
    dispatcher = backend.Dispatcher()
    dispatcher.register(MissingLibraryBackend)
    value = {"numbers": [1, 2, 3]}

    saved_path = dispatcher.save(value, "value")

    assert dispatcher.get_path("value") == saved_path
    assert dispatcher.load("value") == value


def test_disabled_fallback_preserves_import_error(marshal_dir):
    serializer = MissingLibraryBackend()
    serializer.fallback_on_missing_lib = False

    with pytest.raises(ImportError, match="optional serializer unavailable"):
        serializer.wrapped_save({"numbers": [1, 2, 3]}, "value")

    assert list(marshal_dir.iterdir()) == []
    assert not Path("value").exists()
