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

import errno
import hashlib
import json
import logging
import os
import random
import re
import shutil
import string
import sys
from typing import Any
import urllib

import __main__

log = logging.getLogger(__name__)


def get_main_source_path():
    """Get the absolute path to the program entrypoint source."""
    return os.path.abspath(__main__.__file__)


def main_source_lives_in_cwd():
    """Check if the main executable is located at the root of CWD."""
    return os.path.dirname(get_main_source_path()) == os.getcwd()


def random_string(size=5, chars=string.ascii_lowercase + string.digits):
    """Generate random string."""
    return "".join(random.choice(chars) for _ in range(size))


def abs_working_dir(path):
    """Get absolute path to parent dir."""
    abs_path = os.path.abspath(path)
    if os.path.isfile(path):
        abs_path = os.path.dirname(abs_path)
    return abs_path


def rm_r(path, ignore_missing=True, silent=False):
    """Remove a file or directory.

    Similar to rm -r. If the path does not exist and ignore_missing is False,
    OSError is raised, otherwise it is ignored.
    If silent is True, nothing is raised.
    """

    def onerror(function, path, excinfo):
        # Function to handle ENOENT in shutil.rmtree()
        e = excinfo[1]
        if ignore_missing and isinstance(e, OSError) and e.errno == errno.ENOENT:
            return
        raise e

    log.info("Removing path `%s'", path)

    try:
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path, onerror=onerror)
        elif os.path.exists(path) and not silent:
            raise RuntimeError(
                f"Failed to remove path `{path}': Path exists but is not a file nor a directory"
            )
        else:
            # The path does not exists, raise the appropriate exception and let
            # the exception handler handle it (i.e., check ignore_missing etc.)
            raise OSError(errno.ENOENT, "No such file or directory", path)
    except OSError as e:
        if silent:
            log.debug("Path `%s' does not exist, skipping removing it", path)
            return
        if (not ignore_missing) or (e.errno != errno.ENOENT):
            log.error("Failed to remove path `%s' (errno: %s): %s", path, e.errno, e)
            raise


def remove_ansi_color_sequences(text):
    """Remove ANSI color sequences from text."""
    ansi_color_escape = re.compile(r"\x1B\[[0-9;]*m")
    return ansi_color_escape.sub("", text)


def comment_magic_commands(code):
    """Comment the magic commands in a code block."""
    magic_pattern = re.compile(r"^(\s*%%?.*)$", re.MULTILINE)
    return re.sub(magic_pattern, r"#\1", code.strip())


def encode_url_component(component: str):
    """Encode a value so it can safely be used as a URL component."""
    return urllib.parse.quote(component, safe="")


def sanitize_k8s_name(name):
    """Sanitize a string to conform to Kubernetes naming conventions."""
    name = re.sub("-+", "-", re.sub("[^-0-9a-z]+", "-", name.lower()))
    return name.lstrip("-").rstrip("-")


def notebook_k8s_name(notebook_path: str) -> str:
    """Kubernetes-safe name for a notebook: its file name plus a hash of its path."""
    stem = os.path.splitext(os.path.basename(notebook_path))[0]
    digest = hashlib.sha256(os.path.realpath(notebook_path).encode()).hexdigest()[:8]
    return f"{sanitize_k8s_name(stem) or 'notebook'}-{digest}"


def is_ipython() -> bool:
    """Returns whether the code is running in a ipython kernel."""
    try:
        import IPython

        ipy = IPython.get_ipython()
        if ipy is None:
            return False
    except ImportError:
        return False
    return True


def graceful_exit(exit_code):
    """Exit the program gracefully.

    Running the function `sys.exit()` raises a special exception `SystemExit`
    that is not caught by the python REPL, making it exit the program.
    IPython's REPL, instead, does catch `SystemExit`. It displays the message
    and then goes back to the REPL.

    Code that could either run in an IPython kernel (because the Kale pipeline
    was produced from a notebook) or in a standard Python process, needs to
    handle the exit process seamlessly, regardless of where it's running.

    In case the code is running inside an IPython kernel, this function raises
    a `KaleGracefulExit` exception. This exception is expected to ke captured
    inside the `kale.common.jputils.capture_streams` function.
    """
    if is_ipython():
        from kale.common.jputils import KaleGracefulExit

        raise KaleGracefulExit
    else:
        sys.exit(exit_code)


def read_json_from_file(path: str) -> dict:
    """Read a file that contains a JSON object and return it as dictionary."""
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError:
        log.exception("Failed to parse json file %s", path)
        raise


def ensure_or_create_dir(filepath: str):
    """Ensure the dir of a file exists and isdir, or create it.

    Raises:
        RuntimeError: if dirname of filepath exists and is not a directory
    """
    dirname = os.path.dirname(filepath)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    elif not os.path.isdir(dirname):
        raise RuntimeError(f"'{dirname}' is not a directory")


def clean_dir(path: str):
    """If path exists, remove and then create empty dir."""
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)


def shorten_long_string(obj: Any, chars: int = 75):
    """Shorten the string representation of the input object."""
    str_input = str(obj)
    return str_input[:chars] + " ..... " + str_input[len(str_input) - chars :]


def dedent(text: str):
    """Remove longest common prefix consisting of whitespaces.

    Args:
        text: Multiline string
    """
    matches = re.findall(r"(?m)^\s+", text)
    if len(matches) < len(text.splitlines()):
        return text
    return re.sub(r"(?m)^.{%d}" % min(map(len, matches)), "", text)


def compute_pip_index_urls() -> list[str]:
    """Compute the list of pip simple index URLs for generated KFP components.

    Using a local PyPI index is useful when itering on local
    developement with an unpublished version of Kale.

    Precedence:
        1. If `KALE_PIP_INDEX_URLS` is set, split its comma-separated value
        (order preserved) and use it as the base list.
        2. Else, if `KALE_DEV_MODE` is truthy (`1`, `true`, `yes`, or `on`),
        use a base list containing the devpi simple URL
        (`KALE_DEVPI_SIMPLE_URL`) or its default value.
        3. Otherwise, the base list is empty.

        In every case, the production index (`KALE_PYPI_PROD_URL`, defaulting
        to "https://pypi.org/simple") is appended last, de-duplicated if it's
        already present in the base list.

    Environment variables:
        KALE_PIP_INDEX_URLS:
            Comma-separated list of PEP 503 “simple” index URLs. Highest
            priority.
        KALE_DEV_MODE:
            Boolean-like flag enabling dev mode (interprets 1/true/yes/on).
        KALE_DEVPI_SIMPLE_URL:
            Devpi “simple” index URL used when dev mode is enabled.
        KALE_PYPI_PROD_URL:
            Production pip simple index URL. Defaults to
            "https://pypi.org/simple". Useful for air-gapped or
            mirror-only deployments that can't reach public PyPI.

    Returns:
        list[str]: Index URLs suitable for the `pip_index_urls` parameter in
        `@kfp_dsl.component`.
    """
    pypi_prod_url = os.getenv("KALE_PYPI_PROD_URL", "").strip() or "https://pypi.org/simple"
    urls: list[str]

    # explicit override wins
    env_override = os.getenv("KALE_PIP_INDEX_URLS")
    if env_override:
        urls = [u.strip() for u in env_override.split(",") if u.strip()]
    else:
        urls = []
        dev_mode = os.getenv("KALE_DEV_MODE", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if dev_mode:
            urls.append(
                os.getenv(
                    "KALE_DEVPI_SIMPLE_URL",
                    "http://127.0.0.1:3141/root/dev/+simple/",
                )
            )

    # keep the production url last (for package resolution order) and
    # de-duplicated, even if it's already present in the base list.
    urls = [u for u in urls if u != pypi_prod_url]
    urls.append(pypi_prod_url)
    return urls


def compute_trusted_hosts() -> list[str]:
    """Compute the list of trusted hosts for use with pip.

    If user set a comma separated list of hosts using the
    system property KALE_PIP_TRUSTED_HOSTS, then these hosts
    will be used as trusted hosts, otherwise the list will be
    empty.


    :return: The list of trusted hosts configured by the user
    :rtype: list[str]
    """
    pip_trusted_hosts = os.getenv("KALE_PIP_TRUSTED_HOSTS")
    trusted_hosts: list[str] = []
    if pip_trusted_hosts:
        trusted_hosts = [u.strip() for u in pip_trusted_hosts.split(",") if u.strip()]
    return trusted_hosts


def get_default_base_image_from_env() -> str | None:
    """Read the default base image from ``KALE_DEFAULT_BASE_IMAGE``.

    Returns:
        The image reference if the environment variable is set and non-empty,
        otherwise ``None``.
    """
    value = os.getenv("KALE_DEFAULT_BASE_IMAGE")
    if value and value.strip():
        return value.strip()
    return None


def get_security_context_from_env():
    """Read security context configuration from KALE_ environment variables.

    Environment variables:
        KALE_SECURITY_CONTEXT_ENABLED:
            Boolean-like flag (1/true/yes/on) to enable/disable security context.
        KALE_SECURITY_CONTEXT_RUN_AS_USER:
            Integer UID of the users that will be used to run the container.
        KALE_SECURITY_CONTEXT_RUN_AS_GROUP:
            Integer GID of the group that will be used to run the container.
        KALE_SECURITY_CONTEXT_RUN_AS_NON_ROOT:
            Boolean-like flag (1/true/yes/on) to require non-root execution.

    Returns:
        SecurityContextConfig: Security context with config values from environment.
        Only includes keys that were explicitly set via env vars; missing keys mean the caller should use defaults.
    """
    from kale.pipeline import SecurityContextConfig

    def parse_bool(val: str) -> bool:
        return val.lower() in {"1", "true", "yes", "on"}

    security_context = SecurityContextConfig()

    enabled = os.getenv("KALE_SECURITY_CONTEXT_ENABLED")
    run_as_user = os.getenv("KALE_SECURITY_CONTEXT_RUN_AS_USER")
    run_as_group = os.getenv("KALE_SECURITY_CONTEXT_RUN_AS_GROUP")
    run_as_non_root = os.getenv("KALE_SECURITY_CONTEXT_RUN_AS_NON_ROOT")

    if enabled is not None:
        security_context.enabled = parse_bool(enabled)
    if run_as_user is not None:
        try:
            security_context.run_as_user = int(run_as_user)
        except ValueError:
            log.warning(
                "Invalid value for KALE_SECURITY_CONTEXT_RUN_AS_USER: '%s'. "
                "Expected an integer. Ignoring this value.",
                run_as_user,
            )
    if run_as_group is not None:
        try:
            security_context.run_as_group = int(run_as_group)
        except ValueError:
            log.warning(
                "Invalid value for KALE_SECURITY_CONTEXT_RUN_AS_GROUP: '%s'. "
                "Expected an integer. Ignoring this value.",
                run_as_group,
            )
    if run_as_non_root is not None:
        security_context.run_as_non_root = parse_bool(run_as_non_root)
    return security_context
