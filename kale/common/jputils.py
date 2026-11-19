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

import contextlib
import json
import logging
import os
import re
import sys

import ipykernel
from jupyter_client.kernelspec import get_kernel_spec
from jupyter_server import serverapp
from nbconvert.preprocessors.execute import CellExecutionError, ExecutePreprocessor
import nbformat
from packaging import version as pkg_version
import requests

from kale.common.utils import remove_ansi_color_sequences

log = logging.getLogger(__name__)

HTML_TEMPLATE = """
<html><head>
    <style>
        table {
            border: none;
            border-collapse: collapse;
            border-spacing: 0;
            font-size: 14px;
        }
        td,
        th {
            text-align: right;
            vertical-align: middle;
            padding: 0.5em 0.5em;
            line-height: 1.0;
            white-space: nowrap;
            max-width: 100px;
            text-overflow: ellipsis;
            overflow: hidden;
            border: none;
        }
        th {
            font-weight: bold;
        }
        tbody tr:nth-child(odd) {
            background: rgb(245, 245, 245);
        }
    </style>
</head>
<body><div>
%s
</div></body>
</html>
"""

IMAGE_HTML_TEMPLATE = """
<div>
  <p>{}</p>
  <img src="data:image/png;base64, {}" />
</div>
"""

TEXT_HTML_TEMPLATE = """
<div style="margin:10px 0;">
<pre>
{}
</pre>
</div>
"""

STREAM_HTML_TEMPLATE = """
<pre style="margin:0;">
{}
</pre>
"""

STREAM_ERROR_CONTAINER_HTML_TEMPLATE = """
<div style="background:#FFDDDD;">
{}
</div>
"""

JAVASCRIPT_HTML_TEMPLATE = """
<script>
{}
</script>
"""


class KaleGracefulExit(Exception):
    """Raised to exit an IPython process."""

    pass


def generate_html_output(outputs):
    """Transform a notebook cell rich outputs into a html page.

    Args:
        outputs: notebook cell output

    Returns: html multiline string
    """
    if not isinstance(outputs, list):
        raise ValueError(
            f"A notebook's cell outputs must be a valid list. Found {type(outputs)} instead."
        )
    html_body = ""
    # run through the list of outputs
    for o in outputs:
        html = ""
        # the only rich outputs should come from `display_data` and
        # `execution_result` messages. The latter are identical to
        # `display_data` messages, with the addition of an execution_count key.
        output_type = o.get("output_type", None)
        if not output_type:
            raise ValueError(f"Cell output dict has not `output_type` field. Output: {o}")
        if o["output_type"] == "stream":
            if o["name"] == "stdout":
                html = STREAM_HTML_TEMPLATE.format(o["text"])
            if o["name"] == "stderr":
                html = STREAM_ERROR_CONTAINER_HTML_TEMPLATE.format(
                    STREAM_HTML_TEMPLATE.format(o["text"])
                )
        if o["output_type"] in ["display_data", "execute_result"]:
            # check mime-type of content
            # Currently supported MIME types:
            # see: https://ipython.org/ipython-doc/2/api/generated/IPython.core.displaypub.html#IPython.core.displaypub.DisplayPublisher  # noqa: E501
            # text / plain
            # text / html
            # text / markdown
            # text / latex
            # application / json
            # application / javascript
            # image / png
            # image / jpeg
            # image / svg + xml
            data = o["data"]
            # TODO: Generalize to multiple image types (i.e. jpeg and svg+xml)
            if "image/png" in data:
                title = data.get("text/plain", "")
                html += IMAGE_HTML_TEMPLATE.format(title, data["image/png"])

            if "text/html" in data:
                html += data["text/html"]

            if "image/png" not in data and "text/html" not in data and "text/plain" in data:
                html += TEXT_HTML_TEMPLATE.format(data["text/plain"])

            if "application/javascript" in data:
                html += JAVASCRIPT_HTML_TEMPLATE.format(data["application/javascript"])
        html_body += html
    return html_body


def process_outputs(cells):
    """Process a list of cells outputs after execution."""
    html_outputs = [generate_html_output(c.outputs) for c in cells]
    html_outputs = "\n".join(html_outputs).strip()
    if html_outputs == "":
        html_outputs = "This step did not produce any HTML output."
    html_artifact = HTML_TEMPLATE % html_outputs
    return html_artifact


class StreamingExecutePreprocessor(ExecutePreprocessor):
    """ExecutePreprocessor that echoes the kernel's stdout/stderr live."""

    def output(self, outs, msg, display_id, cell_index):
        """Echo stream messages, then store the output as usual."""
        if msg["msg_type"] == "stream":
            content = msg["content"]
            stream = sys.stderr if content["name"] == "stderr" else sys.stdout
            stream.write(content["text"])
            stream.flush()
        return super().output(outs, msg, display_id, cell_index)


def run_code(source: tuple, kernel_name="python3"):
    """Run code blocks inside a jupyter kernel.

    Args:
        source (tuple): source code blocks
        kernel_name: name of the kernel (form the kernel spec) to be created
    """
    log.info("%s Running user code... %s", "-" * 10, "-" * 10)
    log.newline(lines=3)
    import IPython

    if pkg_version.parse(IPython.__version__) < pkg_version.parse("7.6.0"):
        raise RuntimeError(
            f"IPython version {IPython.__version__} not supported."
            " Kale requires at least version 7.6.0."
        )

    # new notebook
    spec = get_kernel_spec(kernel_name)
    notebook = nbformat.v4.new_notebook(
        metadata={
            "kernelspec": {
                "display_name": spec.display_name,
                "language": spec.language,
                "name": kernel_name,
            }
        }
    )
    notebook.cells = [nbformat.v4.new_code_cell(s) for s in source]
    # these parameters are passed to nbconvert.ExecutePreprocessor
    jupyter_execute_kwargs = {
        "timeout": -1,
        "allow_errors": False,
        "store_widget_state": True,
        "kernel_name": kernel_name,
    }

    resources = {}
    # cwd: If supplied, the kernel will run in this directory
    # resources['metadata'] = {'path': cwd}
    ep = StreamingExecutePreprocessor(**jupyter_execute_kwargs)

    # Start preprocessor: run each code cell and capture the output.
    # The preprocessor owns the kernel, so it shuts it down when done,
    # even if a cell fails. A failing cell's error is recorded in its outputs.
    with contextlib.suppress(CellExecutionError):
        ep.preprocess(notebook, resources)

    has_errors = False
    for cell in notebook.cells:
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                has_errors = True

                cell_source = cell.get("source", "")
                source_lines = cell_source.split("\n")
                if len(source_lines) > 5:
                    code_preview = "\n".join(source_lines[:5]) + "\n... (truncated)"
                else:
                    code_preview = cell_source

                error_name = output.get("ename", "Unknown")
                error_value = output.get("evalue", "Unknown error")
                traceback = output.get("traceback", [])

                log.newline(lines=2)
                log.error("%s Cell Execution Error %s", "=" * 10, "=" * 10)
                log.error(f"Error: {error_name}: {error_value}")
                log.error("Failed code block:")
                log.error("-" * 40)
                for line in code_preview.split("\n"):
                    log.error(f"  {line}")
                log.error("-" * 40)
                if traceback:
                    log.error("Traceback:")
                    for tb_line in traceback:
                        clean_line = remove_ansi_color_sequences(tb_line)
                        log.error(clean_line)
                log.error("=" * 50)
                sys.stdout.flush()

    if has_errors:
        log.newline(lines=2)
        log.error("%s Failed to run user code %s", "-" * 10, "-" * 10)
        sys.stdout.flush()
        sys.exit(-1)

    result = process_outputs(notebook.cells)
    log.newline(lines=3)
    log.info("%s Successfully ran user code %s", "-" * 10, "-" * 10)
    sys.stdout.flush()
    return result


def get_notebook_path():
    """Returns the asb path of the Notebook or None if it cannot be determined.

    NOTE: works only when the security is token-based or there is no password
    """
    log.info("Retrieving absolute path of the active notebook")
    connection_file = os.path.basename(ipykernel.get_connection_file())
    try:
        kernel_id = re.search(r"kernel-(.+?)\.json", connection_file).group(1)
    except AttributeError:
        log.error("Could not load kernel id.")
        return None

    for srv in serverapp.list_running_servers():
        sess_url = "{}api/sessions".format(srv["url"])
        # No token and no password
        if srv["token"] == "" and not srv["password"]:
            req = requests.get(sess_url)
        else:
            token_query_param = "?token={}".format(srv["token"])
            req = requests.get(sess_url + token_query_param)
        if req.status_code != 200:
            log.error(f"Session request failed with status code {req.status_code}")
            return None
        try:
            sessions = json.loads(req.text)
        except json.JSONDecodeError as e:
            log.error(f"Could not parse session response: {e}")
            return None
        for sess in sessions:
            if sess["kernel"]["id"] == kernel_id:
                return os.path.join(srv["notebook_dir"], sess["notebook"]["path"])
    return None
