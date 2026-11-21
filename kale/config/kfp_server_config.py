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

import json
import logging
import os
import tempfile
from typing import Any

from kale.config.config import Config, Field

log = logging.getLogger(__name__)

# The single, canonical default namespace used for KFP API operations when the
# user has not configured one anywhere else. This is the *last* fallback in the
# resolution order below.
DEFAULT_NAMESPACE = "kubeflow"

# Environment variable that lets operators/users set the default KFP namespace
# without editing the JSON config file. Handy for shared notebook/CI images that
# run against clusters where KFP lives in different namespaces
# (e.g. "kubeflow" vs "kubeflow-pipelines" vs a custom one).
KFP_NAMESPACE_ENV_VAR = "KALE_KFP_NAMESPACE"


def get_default_namespace() -> str:
    """Return the default KFP namespace to use when none is explicitly set.

    Resolution order (highest priority first):
    1. The ``KALE_KFP_NAMESPACE`` environment variable, if set and non-empty.
    2. The canonical in-code default (``DEFAULT_NAMESPACE``).

    Note this is only the *default*. An explicit value in the JSON config file,
    or an explicit ``namespace=`` argument to ``get_kfp_client()``, still takes
    precedence over whatever this function returns (see ``load_config`` and
    ``kfp_client_factory.get_kfp_client``).
    """
    return os.getenv(KFP_NAMESPACE_ENV_VAR) or DEFAULT_NAMESPACE


class KFPServerConfig(Config):
    """Configuration for KFP server connection.

    auth_config contains references to where credentials can be found:
    - env_var: Name of environment variable containing the credential
    - file_path: Path to file containing the credential
    - token_path: Path to K8s service account token (for SA auth)

    The ``namespace`` field defaults to ``None`` so that a value coming from the
    JSON config file is left untouched, while an unset namespace is resolved in
    ``_postprocess`` via :func:`get_default_namespace` (which honours
    ``KALE_KFP_NAMESPACE`` before falling back to the canonical default).
    """

    host = Field(type=str, default=None)
    auth_type = Field(type=str, default="none")
    auth_config = Field(type=dict, default=None)
    namespace = Field(type=str, default=None)
    ssl_ca_cert = Field(type=str, default=None)

    def _postprocess(self):
        """Resolve the default namespace when the user did not set one.

        Runs after validation on every construction, so callers (``load_config``,
        ``get_kfp_client``, direct instantiation) all get a concrete namespace
        without repeating the fallback logic. A namespace from the config file or
        an explicit argument is already set and left untouched.
        """
        if self.namespace is None:
            self.namespace = get_default_namespace()


def get_config_path() -> str:
    """Get the path to the KFP server configuration file.

    The path can be overridden by setting the KALE_CONFIG_PATH environment variable.
    If not set, defaults to ~/.config/kale/kfp_server_config.json
    """
    env_path = os.getenv("KALE_CONFIG_PATH")
    if env_path:
        return env_path

    kale_dir = os.path.join(os.path.expanduser("~"), ".config/kale")
    return os.path.join(kale_dir, "kfp_server_config.json")


def load_config() -> KFPServerConfig:
    """Load KFP server configuration from disk.

    Returns:
        KFPServerConfig instance. If no config file exists, returns default
        config. In all cases the ``namespace`` is resolved to a concrete value
        using (in priority order) the config file, the ``KALE_KFP_NAMESPACE``
        environment variable, then the canonical in-code default.
    """
    config_path = get_config_path()
    if not os.path.exists(config_path):
        log.debug("No KFP server config found at %s, using defaults", config_path)
        return KFPServerConfig()

    try:
        with open(config_path) as f:
            config_dict = json.load(f)
        log.info("Loaded KFP server config from %s", config_path)
        return KFPServerConfig(**config_dict)
    except (json.JSONDecodeError, OSError, RuntimeError) as e:
        log.warning("Failed to load KFP server config from %s: %s. Using defaults.", config_path, e)
        return KFPServerConfig()


def _validate_auth_config(auth_type: str, auth_config: dict | None) -> None:
    """Validate that auth_config contains only safe references, not actual secrets.

    Raises:
        ValueError: If auth_config contains disallowed fields that might be secrets
    """
    if auth_config is None:
        return

    # Define allowed fields per auth type (references only, no secrets)
    allowed_fields = {
        "kubernetes_service_account_token": {"token_path"},
        "existing_bearer_token": {"env_var", "file_path"},
        "dex": {"env_var", "file_path"},
        "none": set(),
    }

    # Define dangerous fields that suggest secrets are being passed directly
    dangerous_fields = {"token", "cookies", "credentials", "password", "secret"}

    allowed = allowed_fields.get(auth_type, set())
    actual_fields = set(auth_config.keys())

    # Check for dangerous fields
    dangerous_found = actual_fields & dangerous_fields
    if dangerous_found:
        raise ValueError(
            f"auth_config contains fields that look like secrets: {dangerous_found}. "
            f"Use references instead: {allowed}. "
            "Example: {{'env_var': 'KF_PIPELINES_TOKEN'}} or {{'file_path': '/secrets/token'}}"
        )

    # Check for unexpected fields
    unexpected = actual_fields - allowed
    if unexpected:
        raise ValueError(
            f"auth_config contains unexpected fields: {unexpected}. "
            f"Allowed fields for {auth_type}: {allowed}"
        )


def save_config(config: KFPServerConfig | dict[str, Any]) -> None:
    """Save KFP server configuration to disk.

    Args:
        config: KFPServerConfig instance or dict with config values

    Raises:
        ValueError: If auth_config contains actual secrets instead of references
    """
    if isinstance(config, dict):
        config = KFPServerConfig(**config)

    # Validate auth_config before saving to prevent secrets in config file
    _validate_auth_config(config.auth_type, config.auth_config)

    config_path = get_config_path()
    kale_dir = os.path.dirname(config_path)

    # Create .config/kale directory if it doesn't exist
    os.makedirs(kale_dir, exist_ok=True)

    config_dict = config.to_dict()

    # Create temp file with secure permissions (0o600) from creation
    fd, temp_path = tempfile.mkstemp(dir=kale_dir, prefix=".kfp_server_config.", suffix=".tmp")

    try:
        with os.fdopen(fd, "w") as f:
            json.dump(config_dict, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Ensure data written to disk

        os.replace(temp_path, config_path)
        log.info("Saved KFP server config to %s", config_path)

    except Exception:
        # Clean up temp file on any failure
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
