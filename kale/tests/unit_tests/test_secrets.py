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

from kale.config.validators import K8sSecretsValidator
from kale.processors.nbprocessor import NotebookConfig
from kale.step import Step, StepConfig


class TestK8sSecretsValidator:
    """Tests for the K8sSecretsValidator."""

    def test_valid_secrets(self):
        """A well-formed secrets dict should validate without raising."""
        K8sSecretsValidator()(
            {"DB_PASSWORD": {"secret_name": "db-credentials", "secret_key": "password"}}
        )

    def test_empty_secrets(self):
        """An empty secrets dict should validate without raising."""
        K8sSecretsValidator()({})

    def test_invalid_env_var_name(self):
        """Env var names must match [a-zA-Z_][a-zA-Z0-9_]*."""
        with pytest.raises(ValueError):
            K8sSecretsValidator()(
                {"1_INVALID": {"secret_name": "db-credentials", "secret_key": "password"}}
            )

    def test_invalid_secret_name(self):
        """Secret names must be valid K8s resource names (lowercase RFC1123)."""
        with pytest.raises(ValueError):
            K8sSecretsValidator()(
                {"DB_PASSWORD": {"secret_name": "DB-Credentials", "secret_key": "password"}}
            )

    def test_dotted_secret_name(self):
        """Secret names are DNS subdomains, so dots are allowed."""
        K8sSecretsValidator()(
            {"DB_PASSWORD": {"secret_name": "my.db-credentials", "secret_key": "password"}}
        )

    def test_invalid_secret_key(self):
        """Secret keys must match the allowed key charset."""
        with pytest.raises(ValueError):
            K8sSecretsValidator()(
                {"DB_PASSWORD": {"secret_name": "db-credentials", "secret_key": "pass word"}}
            )

    def test_missing_required_subkey(self):
        """Each secret reference must have both secret_name and secret_key."""
        with pytest.raises(ValueError):
            K8sSecretsValidator()({"DB_PASSWORD": {"secret_name": "db-credentials"}})


class TestStepConfigSecrets:
    """Tests for the `secrets` field on StepConfig."""

    def test_default_empty(self):
        """Secrets default to an empty dict when not provided."""
        config = StepConfig(name="test")
        assert config.secrets == {}

    def test_custom_secrets(self):
        """A valid secrets dict is accepted and preserved."""
        secrets = {"DB_PASSWORD": {"secret_name": "db-credentials", "secret_key": "password"}}
        config = StepConfig(name="test", secrets=secrets)
        assert config.secrets == secrets

    def test_invalid_secrets_raise(self):
        """Malformed secrets should be rejected at Step construction time."""
        with pytest.raises(ValueError):
            Step(
                name="test",
                source=["x = 1"],
                secrets={"DB_PASSWORD": {"secret_name": "Bad-Name", "secret_key": "password"}},
            )


class TestStepsDefaultsSecret:
    """Tests for a `secret:` tag applied as a pipeline-wide steps default."""

    def test_secret_steps_default(self):
        """A `secret:` steps-default tag populates config.steps_defaults."""
        config = NotebookConfig(
            notebook_path="/path/to/nb",
            pipeline_name="test",
            experiment_name="test",
            steps_defaults=["secret:db-credentials:password:DB_PASSWORD"],
        )

        assert config.steps_defaults["secrets"] == {
            "DB_PASSWORD": {"secret_name": "db-credentials", "secret_key": "password"}
        }
