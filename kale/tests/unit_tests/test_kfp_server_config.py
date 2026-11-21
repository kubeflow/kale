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
import os

import pytest
from testfixtures import mock

from kale.common import kfp_client_factory
from kale.config import kfp_server_config
from kale.config.kfp_server_config import KFPServerConfig


def test_get_config_path_default():
    """Test that default config path is returned when no env var is set."""
    with mock.patch.dict(os.environ, {}, clear=True):
        path = kfp_server_config.get_config_path()
        assert path.endswith(".config/kale/kfp_server_config.json")
        assert os.path.expanduser("~") in path


def test_get_config_path_env_override():
    """Test that KALE_CONFIG_PATH env var overrides default path."""
    custom_path = "/custom/path/to/config.json"
    with mock.patch.dict(os.environ, {"KALE_CONFIG_PATH": custom_path}):
        path = kfp_server_config.get_config_path()
        assert path == custom_path


def test_load_config_no_file(tmpdir):
    """Test that default config is returned when no file exists."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        config = kfp_server_config.load_config()

    # Should return default values
    assert config.host is None
    assert config.auth_type == "none"
    assert config.auth_config is None
    assert config.namespace == "kubeflow"
    assert config.ssl_ca_cert is None


def test_load_config_valid(tmpdir):
    """Test that valid config is loaded successfully."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")
    test_config = {
        "host": "http://localhost:8080",
        "auth_type": "existing_bearer_token",
        "auth_config": {"env_var": "TEST_TOKEN"},
        "namespace": "custom-namespace",
        "ssl_ca_cert": "/path/to/cert",
    }

    # Write config file
    with open(config_path, "w") as f:
        json.dump(test_config, f)

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        config = kfp_server_config.load_config()

    assert config.host == "http://localhost:8080"
    assert config.auth_type == "existing_bearer_token"
    assert config.auth_config == {"env_var": "TEST_TOKEN"}
    assert config.namespace == "custom-namespace"
    assert config.ssl_ca_cert == "/path/to/cert"


def test_load_config_malformed_json(tmpdir):
    """Test that defaults are returned on malformed JSON (with warning logged)."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")

    # Write malformed JSON
    with open(config_path, "w") as f:
        f.write("{invalid json")

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        config = kfp_server_config.load_config()

    # Should return defaults when JSON is malformed
    assert config.host is None
    assert config.auth_type == "none"
    assert config.auth_config is None
    assert config.namespace == "kubeflow"
    assert config.ssl_ca_cert is None


def test_load_config_read_error(tmpdir):
    """Test that defaults are returned on file read error (with warning logged)."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")

    # Create file and make it unreadable
    with open(config_path, "w") as f:
        json.dump({"host": "test"}, f)
    os.chmod(config_path, 0o000)

    try:
        with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
            config = kfp_server_config.load_config()

        # Should return defaults when file cannot be read
        assert config.host is None
        assert config.auth_type == "none"
        assert config.auth_config is None
        assert config.namespace == "kubeflow"
        assert config.ssl_ca_cert is None
    finally:
        # Restore permissions for cleanup
        os.chmod(config_path, 0o600)


def test_save_config_creates_directory(tmpdir):
    """Test that .config/kale directory is created if it doesn't exist."""
    config_path = os.path.join(tmpdir, ".config/kale", "kfp_server_config.json")
    test_config = {"host": "http://localhost:8080"}

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        kfp_server_config.save_config(test_config)

    # Directory and file should exist
    assert os.path.exists(os.path.dirname(config_path))
    assert os.path.exists(config_path)


def test_save_config_from_dict(tmpdir):
    """Test that config can be saved from a dictionary."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")
    test_config = {
        "host": "http://localhost:8080",
        "namespace": "custom-namespace",
    }

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        kfp_server_config.save_config(test_config)

    with open(config_path) as f:
        saved = json.load(f)

    assert saved["host"] == "http://localhost:8080"
    assert saved["namespace"] == "custom-namespace"


def test_save_config_from_object(tmpdir):
    """Test that config can be saved from KFPServerConfig object."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")
    test_config = KFPServerConfig(
        host="http://localhost:8080",
        auth_type="dex",
        auth_config={"env_var": "TEST_COOKIES"},
        namespace="custom-namespace",
    )

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        kfp_server_config.save_config(test_config)

    with open(config_path) as f:
        saved = json.load(f)

    assert saved["host"] == "http://localhost:8080"
    assert saved["auth_type"] == "dex"
    assert saved["auth_config"] == {"env_var": "TEST_COOKIES"}
    assert saved["namespace"] == "custom-namespace"


def test_save_config_file_permissions(tmpdir):
    """Test that saved config file has correct permissions (0o600)."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")
    test_config = {"host": "http://localhost:8080"}

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        kfp_server_config.save_config(test_config)

    file_stat = os.stat(config_path)
    # 0o600 means only owner can read/write
    assert file_stat.st_mode & 0o777 == 0o600


def test_config_persistence(tmpdir):
    """Test that saved config persists across save/load cycles."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")
    original_config = {
        "host": "http://localhost:8080",
        "auth_type": "existing_bearer_token",
        "auth_config": {"env_var": "TEST_TOKEN"},
        "namespace": "custom-namespace",
        "ssl_ca_cert": "/path/to/cert",
    }

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        # Save config
        kfp_server_config.save_config(original_config)

        # Load config
        loaded_config = kfp_server_config.load_config()

        # Verify all fields match
        assert loaded_config.host == original_config["host"]
        assert loaded_config.auth_type == original_config["auth_type"]
        assert loaded_config.auth_config == original_config["auth_config"]
        assert loaded_config.namespace == original_config["namespace"]
        assert loaded_config.ssl_ca_cert == original_config["ssl_ca_cert"]

        # Save again with modified values
        modified_config = {**original_config, "host": "http://new-host:9090"}
        kfp_server_config.save_config(modified_config)

        # Load again and verify changes
        reloaded_config = kfp_server_config.load_config()
        assert reloaded_config.host == "http://new-host:9090"
        assert reloaded_config.auth_type == original_config["auth_type"]


@mock.patch("kale.common.kfp_client_factory.kfp.Client")
@mock.patch("kale.common.kfp_authenticator.get_authenticator")
def test_get_kfp_client_with_saved_config(mock_get_auth, mock_client, tmpdir):
    """Test that get_kfp_client uses saved configuration."""
    from kale.common.kfp_authenticator import AuthResult

    config_path = os.path.join(tmpdir, "kfp_server_config.json")
    saved_config = {
        "host": "http://saved-host:8080",
        "auth_type": "dex",
        "auth_config": {"env_var": "TEST_COOKIES"},
        "namespace": "saved-namespace",
    }

    # Save config
    with open(config_path, "w") as f:
        json.dump(saved_config, f)

    # Mock authenticator to return cookies (simulating resolution from env var)
    mock_authenticator = mock.Mock()
    mock_authenticator.authenticate.return_value = AuthResult(cookies="resolved_cookie_value")
    mock_get_auth.return_value = mock_authenticator

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        kfp_client_factory.get_kfp_client()

    # Verify authenticator was called with config reference (not actual cookie)
    mock_get_auth.assert_called_once_with("dex")
    mock_authenticator.authenticate.assert_called_once_with({"env_var": "TEST_COOKIES"})

    # Verify kfp.Client was called with resolved auth result
    mock_client.assert_called_once_with(
        host="http://saved-host:8080",
        cookies="resolved_cookie_value",
        credentials=None,
        existing_token=None,
        namespace="saved-namespace",
        ssl_ca_cert=None,
    )


@mock.patch("kale.common.kfp_client_factory.kfp.Client")
@mock.patch("kale.common.kfp_authenticator.get_authenticator")
def test_get_kfp_client_parameter_override(mock_get_auth, mock_client, tmpdir):
    """Test that explicit parameters override saved config."""
    from kale.common.kfp_authenticator import AuthResult

    config_path = os.path.join(tmpdir, "kfp_server_config.json")
    saved_config = {
        "host": "http://saved-host:8080",
        "auth_type": "dex",
        "auth_config": {"env_var": "TEST_COOKIES"},
        "namespace": "saved-namespace",
    }

    # Save config
    with open(config_path, "w") as f:
        json.dump(saved_config, f)

    # Mock authenticator for override auth
    mock_authenticator = mock.Mock()
    mock_authenticator.authenticate.return_value = AuthResult(existing_token="resolved_token_value")
    mock_get_auth.return_value = mock_authenticator

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        # Call with explicit parameters that should override
        kfp_client_factory.get_kfp_client(
            host="http://override-host:9090",
            auth_type="existing_bearer_token",
            auth_config={"env_var": "OVERRIDE_TOKEN"},
            namespace="override-namespace",
        )

    # Verify authenticator was called with override config
    mock_get_auth.assert_called_once_with("existing_bearer_token")
    mock_authenticator.authenticate.assert_called_once_with({"env_var": "OVERRIDE_TOKEN"})

    # Verify kfp.Client was called with resolved token from override config
    mock_client.assert_called_once_with(
        host="http://override-host:9090",
        cookies=None,
        credentials=None,
        existing_token="resolved_token_value",
        namespace="override-namespace",
        ssl_ca_cert=None,
    )


@mock.patch("kale.common.kfp_client_factory.kfp.Client")
@mock.patch("kale.common.kfp_authenticator.get_authenticator")
def test_get_kfp_client_default_behavior(mock_get_auth, mock_client, tmpdir):
    """Test default behavior when no config and no parameters provided."""
    from kale.common.kfp_authenticator import AuthResult

    config_path = os.path.join(tmpdir, "kfp_server_config.json")

    # Mock authenticator for "none" auth type
    mock_authenticator = mock.Mock()
    mock_authenticator.authenticate.return_value = AuthResult()
    mock_get_auth.return_value = mock_authenticator

    # No config file exists
    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        kfp_client_factory.get_kfp_client()

    # Verify authenticator was called with "none" (default)
    mock_get_auth.assert_called_once_with("none")

    # Verify kfp.Client was called with defaults (None for host allows in-cluster discovery)
    mock_client.assert_called_once_with(
        host=None,
        cookies=None,
        credentials=None,
        existing_token=None,
        namespace="kubeflow",
        ssl_ca_cert=None,
    )


@mock.patch("kale.common.kfp_client_factory.kfp.Client")
@mock.patch("kale.common.kfp_authenticator.get_authenticator")
def test_get_kfp_client_all_parameters(mock_get_auth, mock_client, tmpdir):
    """Test that all parameters are correctly passed to kfp.Client."""
    from kale.common.kfp_authenticator import AuthResult

    config_path = os.path.join(tmpdir, "kfp_server_config.json")

    # Mock authenticator
    mock_authenticator = mock.Mock()
    mock_authenticator.authenticate.return_value = AuthResult(existing_token="resolved_test_token")
    mock_get_auth.return_value = mock_authenticator

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        kfp_client_factory.get_kfp_client(
            host="http://test-host:8080",
            auth_type="existing_bearer_token",
            auth_config={"env_var": "TEST_TOKEN"},
            namespace="test_namespace",
            ssl_ca_cert="/path/to/cert",
        )

    # Verify authenticator was used with config reference
    mock_get_auth.assert_called_once_with("existing_bearer_token")
    mock_authenticator.authenticate.assert_called_once_with({"env_var": "TEST_TOKEN"})

    # Verify all parameters were passed correctly with resolved token
    mock_client.assert_called_once_with(
        host="http://test-host:8080",
        cookies=None,
        credentials=None,
        existing_token="resolved_test_token",
        namespace="test_namespace",
        ssl_ca_cert="/path/to/cert",
    )


def test_save_config_rejects_direct_token(tmpdir):
    """Test that saving actual token in auth_config is rejected."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")

    with (
        mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path),
        pytest.raises(ValueError, match="contains fields that look like secrets"),
    ):
        kfp_server_config.save_config(
            {
                "auth_type": "existing_bearer_token",
                "auth_config": {"token": "secret-123"},  # ← Should fail
            }
        )


def test_save_config_rejects_direct_cookies(tmpdir):
    """Test that saving actual cookies in auth_config is rejected."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")

    with (
        mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path),
        pytest.raises(ValueError, match="contains fields that look like secrets"),
    ):
        kfp_server_config.save_config(
            {
                "auth_type": "dex",
                "auth_config": {"cookies": "session=abc"},  # ← Should fail
            }
        )


def test_save_config_accepts_env_var_reference(tmpdir):
    """Test that env var reference is accepted."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        # Should NOT raise
        kfp_server_config.save_config(
            {
                "auth_type": "existing_bearer_token",
                "auth_config": {"env_var": "KF_PIPELINES_TOKEN"},  # ← OK
            }
        )

    # Verify it was saved correctly
    with open(config_path) as f:
        saved = json.load(f)
    assert saved["auth_config"] == {"env_var": "KF_PIPELINES_TOKEN"}


def test_save_config_accepts_file_path_reference(tmpdir):
    """Test that file path reference is accepted."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")

    with mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path):
        # Should NOT raise
        kfp_server_config.save_config(
            {
                "auth_type": "existing_bearer_token",
                "auth_config": {"file_path": "/secrets/token"},  # ← OK
            }
        )

    # Verify it was saved correctly
    with open(config_path) as f:
        saved = json.load(f)
    assert saved["auth_config"] == {"file_path": "/secrets/token"}


def test_save_config_rejects_unexpected_fields(tmpdir):
    """Test that unexpected fields in auth_config are rejected."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")

    with (
        mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path),
        pytest.raises(ValueError, match="unexpected fields"),
    ):
        kfp_server_config.save_config(
            {
                "auth_type": "existing_bearer_token",
                "auth_config": {"random_field": "value"},  # ← Should fail
            }
        )


def test_bearer_token_file_path_takes_precedence_over_env_var(tmpdir):
    """Test that configured file_path is used even when env var exists."""
    from kale.common.kfp_authenticator import ExistingBearerTokenAuthenticator

    # Create a token file
    token_file = os.path.join(tmpdir, "token.txt")
    with open(token_file, "w") as f:
        f.write("file-token-content")

    # Set environment variable
    with mock.patch.dict(os.environ, {"KF_PIPELINES_TOKEN": "env-token-content"}):
        authenticator = ExistingBearerTokenAuthenticator()
        result = authenticator.authenticate({"file_path": token_file})

        # Should use file content, not env var
        assert result.existing_token == "file-token-content"
        assert result.cookies is None
        assert result.credentials is None


def test_bearer_token_env_var_used_when_no_file_path(tmpdir):
    """Test that env var is used when file_path is not configured."""
    from kale.common.kfp_authenticator import ExistingBearerTokenAuthenticator

    # Set environment variable
    with mock.patch.dict(os.environ, {"KF_PIPELINES_TOKEN": "env-token-content"}):
        authenticator = ExistingBearerTokenAuthenticator()
        result = authenticator.authenticate({})  # No file_path configured

        # Should use env var
        assert result.existing_token == "env-token-content"
        assert result.cookies is None
        assert result.credentials is None


def test_k8s_sa_token_path_config_takes_precedence_over_env_var(tmpdir):
    """Test that configured token_path is used even when env var exists."""
    from kale.common.kfp_authenticator import K8sServiceAccountTokenAuthenticator

    # Create two token files
    config_token_file = os.path.join(tmpdir, "config-token")
    env_token_file = os.path.join(tmpdir, "env-token")

    with open(config_token_file, "w") as f:
        f.write("config-token-content")
    with open(env_token_file, "w") as f:
        f.write("env-token-content")

    # Set environment variable pointing to env_token_file
    with (
        mock.patch.dict(os.environ, {"KF_PIPELINES_SA_TOKEN_PATH": env_token_file}),
        mock.patch("kfp.client.ServiceAccountTokenVolumeCredentials") as mock_sa_creds,
    ):
        authenticator = K8sServiceAccountTokenAuthenticator()
        result = authenticator.authenticate({"token_path": config_token_file})

        # Should use config path, not env var path
        # Verify ServiceAccountTokenVolumeCredentials was called with config path
        mock_sa_creds.assert_called_once_with(path=config_token_file)
        assert result.credentials is not None
        assert result.cookies is None
        assert result.existing_token is None


def test_k8s_sa_token_path_env_var_used_when_no_config(tmpdir):
    """Test that env var is used when token_path is not configured."""
    from kale.common.kfp_authenticator import K8sServiceAccountTokenAuthenticator

    # Create token file
    env_token_file = os.path.join(tmpdir, "env-token")
    with open(env_token_file, "w") as f:
        f.write("env-token-content")

    # Set environment variable
    with (
        mock.patch.dict(os.environ, {"KF_PIPELINES_SA_TOKEN_PATH": env_token_file}),
        mock.patch("kfp.client.ServiceAccountTokenVolumeCredentials") as mock_sa_creds,
    ):
        authenticator = K8sServiceAccountTokenAuthenticator()
        result = authenticator.authenticate({})  # No token_path configured

        # Should use env var path
        # Verify ServiceAccountTokenVolumeCredentials was called with env var path
        mock_sa_creds.assert_called_once_with(path=env_token_file)
        assert result.credentials is not None
        assert result.cookies is None
        assert result.existing_token is None


# ---------------------------------------------------------------------------
# KALE_KFP_NAMESPACE support (issue #798)
#
# Resolution order for the KFP client namespace (highest priority first):
#   1. explicit namespace= argument to get_kfp_client()
#   2. "namespace" in the JSON config file
#   3. KALE_KFP_NAMESPACE environment variable
#   4. the canonical in-code default (kfp_server_config.DEFAULT_NAMESPACE)
# ---------------------------------------------------------------------------


def test_get_default_namespace_unset_env():
    """With KALE_KFP_NAMESPACE unset, the canonical in-code default is used."""
    with mock.patch.dict(os.environ, {}, clear=True):
        assert kfp_server_config.get_default_namespace() == kfp_server_config.DEFAULT_NAMESPACE


def test_get_default_namespace_env_override():
    """KALE_KFP_NAMESPACE overrides the canonical in-code default."""
    with mock.patch.dict(os.environ, {"KALE_KFP_NAMESPACE": "ml-pipelines"}):
        assert kfp_server_config.get_default_namespace() == "ml-pipelines"


def test_load_config_no_file_uses_env_namespace(tmpdir):
    """When no config file exists, KALE_KFP_NAMESPACE sets the namespace."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")

    with (
        mock.patch.dict(os.environ, {"KALE_KFP_NAMESPACE": "ml-pipelines"}),
        mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path),
    ):
        config = kfp_server_config.load_config()

    assert config.namespace == "ml-pipelines"


def test_load_config_file_namespace_wins_over_env(tmpdir):
    """A namespace in the config file takes precedence over the env var."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")
    with open(config_path, "w") as f:
        json.dump({"namespace": "from-file"}, f)

    with (
        mock.patch.dict(os.environ, {"KALE_KFP_NAMESPACE": "from-env"}),
        mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path),
    ):
        config = kfp_server_config.load_config()

    assert config.namespace == "from-file"


def test_load_config_file_without_namespace_falls_back_to_env(tmpdir):
    """A config file that omits 'namespace' still honours KALE_KFP_NAMESPACE."""
    config_path = os.path.join(tmpdir, "kfp_server_config.json")
    with open(config_path, "w") as f:
        json.dump({"host": "http://localhost:8080"}, f)

    with (
        mock.patch.dict(os.environ, {"KALE_KFP_NAMESPACE": "from-env"}),
        mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path),
    ):
        config = kfp_server_config.load_config()

    assert config.host == "http://localhost:8080"
    assert config.namespace == "from-env"


@mock.patch("kale.common.kfp_client_factory.kfp.Client")
@mock.patch("kale.common.kfp_authenticator.get_authenticator")
def test_get_kfp_client_uses_env_namespace(mock_get_auth, mock_client, tmpdir):
    """get_kfp_client() picks up KALE_KFP_NAMESPACE when nothing else is set."""
    from kale.common.kfp_authenticator import AuthResult

    config_path = os.path.join(tmpdir, "kfp_server_config.json")  # no file created

    mock_authenticator = mock.Mock()
    mock_authenticator.authenticate.return_value = AuthResult()
    mock_get_auth.return_value = mock_authenticator

    with (
        mock.patch.dict(os.environ, {"KALE_KFP_NAMESPACE": "ml-pipelines"}),
        mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path),
    ):
        kfp_client_factory.get_kfp_client()

    _, kwargs = mock_client.call_args
    assert kwargs["namespace"] == "ml-pipelines"


@mock.patch("kale.common.kfp_client_factory.kfp.Client")
@mock.patch("kale.common.kfp_authenticator.get_authenticator")
def test_get_kfp_client_param_overrides_env_namespace(mock_get_auth, mock_client, tmpdir):
    """An explicit namespace= argument wins over KALE_KFP_NAMESPACE."""
    from kale.common.kfp_authenticator import AuthResult

    config_path = os.path.join(tmpdir, "kfp_server_config.json")  # no file created

    mock_authenticator = mock.Mock()
    mock_authenticator.authenticate.return_value = AuthResult()
    mock_get_auth.return_value = mock_authenticator

    with (
        mock.patch.dict(os.environ, {"KALE_KFP_NAMESPACE": "from-env"}),
        mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path),
    ):
        kfp_client_factory.get_kfp_client(namespace="explicit-namespace")

    _, kwargs = mock_client.call_args
    assert kwargs["namespace"] == "explicit-namespace"


@mock.patch("kale.common.kfp_client_factory.kfp.Client")
@mock.patch("kale.common.kfp_authenticator.get_authenticator")
def test_get_kfp_client_default_namespace_when_env_unset(mock_get_auth, mock_client, tmpdir):
    """With no file, no param and no env var, the canonical default is used."""
    from kale.common.kfp_authenticator import AuthResult

    config_path = os.path.join(tmpdir, "kfp_server_config.json")  # no file created

    mock_authenticator = mock.Mock()
    mock_authenticator.authenticate.return_value = AuthResult()
    mock_get_auth.return_value = mock_authenticator

    with (
        mock.patch.dict(os.environ, {}, clear=True),
        mock.patch("kale.config.kfp_server_config.get_config_path", return_value=config_path),
    ):
        kfp_client_factory.get_kfp_client()

    _, kwargs = mock_client.call_args
    assert kwargs["namespace"] == kfp_server_config.DEFAULT_NAMESPACE
