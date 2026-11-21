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

"""Factory for creating KFP client instances with configuration support."""

from typing import TYPE_CHECKING

import kfp

from kale.common import kfp_authenticator
from kale.config import kfp_server_config

if TYPE_CHECKING:
    from kfp import Client


def get_kfp_client(
    host: str | None = None,
    auth_type: str | None = None,
    auth_config: dict | None = None,
    namespace: str | None = None,
    ssl_ca_cert: str | None = None,
) -> "Client":
    """Create a KFP client with configuration.

    Loads saved configuration from ~/.config/kale/kfp_server_config.json and allows
    parameter overrides. Explicit parameters override saved config if they are provided.

    Authentication is handled by creating credentials at runtime using the authenticator
    module. Credentials are NEVER stored in config - only references to where they
    can be found (env vars, file paths).

    Args:
        host: KFP API server host
        auth_type: Authentication type. Supported values:
            - "kubernetes_service_account_token": K8s service account token
            - "existing_bearer_token": Pre-existing bearer token
            - "dex": DEX cookie-based authentication
            - "none": No authentication (default)
        auth_config: Configuration references for authentication:
            - {"env_var": "VAR_NAME"}: Read credential from environment variable
            - {"file_path": "/path/to/file"}: Read credential from file
            - {"token_path": "/path/to/token"}: K8s SA token path (SA auth only)
        namespace: Kubernetes namespace for KFP API operations. If not
            provided, falls back to the saved config, then the
            KALE_KFP_NAMESPACE environment variable, then the canonical
            in-code default (see kfp_server_config.get_default_namespace).
        ssl_ca_cert: Path to CA certificate file

    Returns:
        kfp.Client instance configured with provided parameters or saved config
    """
    # Load saved configuration
    config = kfp_server_config.load_config()

    # Use parameter if provided, otherwise fall back to config.
    # Note: config.namespace is already resolved by load_config() to a concrete
    # value (config file -> KALE_KFP_NAMESPACE env var -> canonical default), so
    # there is no hardcoded namespace fallback here anymore. An explicit
    # `namespace=` argument still wins over everything.
    host = host or config.host
    auth_type = auth_type or config.auth_type or "none"
    auth_config = auth_config or config.auth_config or {}
    namespace = namespace or config.namespace
    ssl_ca_cert = ssl_ca_cert or config.ssl_ca_cert

    # Create credentials at runtime using authenticator
    authenticator = kfp_authenticator.get_authenticator(auth_type)
    auth_result = authenticator.authenticate(auth_config)

    return kfp.Client(
        host=host,
        credentials=auth_result.credentials,
        cookies=auth_result.cookies,
        existing_token=auth_result.existing_token,
        namespace=namespace,
        ssl_ca_cert=ssl_ca_cert,
    )
