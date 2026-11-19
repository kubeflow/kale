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
from testfixtures import mock

from kale.common import jputils as ju


def _output_display(data):
    # `data` must be a list
    return [{"output_type": "display_data", "data": data}]


@pytest.mark.parametrize(
    "outputs,target",
    [
        ([], ""),
        # ---
        (_output_display({"image/png": "bytes"}), ju.IMAGE_HTML_TEMPLATE.format("", "bytes")),
        # ---
        (_output_display({"text/html": "bytes"}), "bytes"),
        # ---
        (_output_display({"text/plain": "bytes"}), ju.TEXT_HTML_TEMPLATE.format("bytes")),
        # ---
        (
            _output_display({"application/javascript": "bytes"}),
            ju.JAVASCRIPT_HTML_TEMPLATE.format("bytes"),
        ),
    ],
)
def test_generate_html_output(outputs, target):
    """Tests html artifact generation from cell outputs."""
    assert target == ju.generate_html_output(outputs)


@mock.patch("kale.common.jputils.process_outputs", new=lambda x: x)
def test_run_code():
    """Test that Python code runs inside a jupyter kernel successfully."""
    # test standard code
    code = ("a = 3\nprint(a)",)
    ju.run_code(code)

    # test magic command
    code = ("%%time\nprint('Some dull code')",)
    ju.run_code(code)


def test_run_code_captures_stdout_and_stderr(capsys):
    """Test that stdout and stderr from executed code reach the caller."""
    code = (
        "print('stdout-marker')",
        "import sys\nprint('stderr-marker', file=sys.stderr)",
    )

    ju.run_code(code)

    captured = capsys.readouterr()
    assert "stdout-marker" in captured.out
    assert "stderr-marker" in captured.err


def test_run_code_stops_after_first_error(tmp_path):
    """Test that execution stops when a code cell raises an exception."""
    marker = tmp_path / "ran_after_error"

    code = (
        "raise ValueError('boom')",
        f"open({str(marker)!r}, 'w').close()",
    )

    with pytest.raises(SystemExit) as exc_info:
        ju.run_code(code)

    assert exc_info.value.code == -1
    assert not marker.exists()
