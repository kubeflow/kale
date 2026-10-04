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

from abc import ABC, abstractmethod
import re
from typing import Any


class Validator(ABC):
    """Base validator class.

    All Validator classes must inherit from this one.
    """

    @abstractmethod
    def _validate(self, *args, **kwargs) -> bool:
        pass

    def __call__(self, *args, **kwargs):
        """Run validation."""
        self._validate(*args, **kwargs)


class TypeValidator(Validator):
    """Validates a Field based on a primitive type."""

    valid_type = None

    def __init__(self, valid_type: type):
        self.valid_type = valid_type or self.valid_type
        if not self.valid_type:
            raise ValueError("Not a valid type")

    def _validate(self, value):
        if not isinstance(value, self.valid_type):
            raise ValueError(f"'{value}' must be of type '{self.valid_type}'")


class DictValidator(Validator):
    """Validates a dictionary, applying `key` and `value` validators."""

    key_validator = None
    value_validator = None

    def __init__(self, key_validator: Validator = None, value_validator: Validator = None):
        self.key_validator = key_validator or self.key_validator
        if not self.key_validator:
            raise ValueError("Set an appropriate key_validator")
        self.value_validator = value_validator or self.value_validator
        if not self.value_validator:
            raise ValueError("Set an appropriate value_validator")

    def _validate(self, dictionary: dict):
        if not isinstance(dictionary, dict):
            raise ValueError(
                f"Trying to use {self.__class__.__name__} to validate a non dict object"
            )
        for k, v in dictionary.items():
            self.key_validator(k)
            self.value_validator(v)
        return True


class RegexValidator(Validator):
    """Validates a string against a RegEx."""

    regex = None
    error_message = "Regex validation failed"

    def __init__(self, regex: str = None, error_message: str = None):
        self.regex = regex or self.regex
        if not self.regex:
            raise ValueError("Invalid 'regex' argument")

        self.error_message = error_message or self.error_message

    def _validate(self, value: str):
        if not isinstance(value, str):
            raise ValueError(
                f"{self.__class__.__name__} cannot validate object of type {str(type(value))}. String expected."
            )
        if not re.match(self.regex, value):
            raise ValueError(f"{self.error_message}: '{value}'. Must match regex '{self.regex}'")
        return True


class EnumValidator(Validator):
    """Validates a value against a whitelist."""

    enum = None

    def __init__(self, enum: tuple = None):
        self.enum = enum or self.enum
        if not self.enum:
            raise ValueError("Invalid 'enum' argument")

    def _validate(self, value: Any):
        if value not in self.enum:
            raise ValueError(f"{self.__class__.__name__}: Value {str(value)} is not allowed")


class K8sNameValidator(RegexValidator):
    """Validates K8s resource names."""

    regex = r"^[a-z]([a-z0-9-]*[a-z0-9])?$"
    error_message = "Not a valid K8s resource name"


class StepNameValidator(RegexValidator):
    """Validates the name of a pipeline step."""

    regex = r"^[_a-z]([_a-z0-9]*)?$"
    error_message = "Not a valid Step name"


class PipelineNameValidator(RegexValidator):
    """Validates the name of a pipeline."""

    regex = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
    error_message = "Not a valid Pipeline name"


class K8sAnnotationKeyValidator(RegexValidator):
    """Validates the keys of a K8s annotations dictionary."""

    _segment = "[a-zA-Z0-9]+([a-zA-Z0-9-_.]*[a-zA-Z0-9])?"
    regex = rf"^{_segment}([/]{_segment})?$"
    error_message = "Not a valid K8s annotation key"


class K8sAnnotationsValidator(DictValidator):
    """Validates a K8s annotations dictionary."""

    key_validator = K8sAnnotationKeyValidator
    value_validator = TypeValidator(str)


class K8sLimitKeyValidator(RegexValidator):
    """Validates the keys of a K8s limits dictionary."""

    regex = r"[_a-z-\.\/]+"
    error_message = "Not a valid K8s limit key"


class K8sLimitValueValidator(RegexValidator):
    """Validates the values of a K8s limits dictionary."""

    regex = r"^[_a-zA-Z0-9\.]+$"
    error_message = "Not a valid K8s limit value"


class K8sLimitsValidator(DictValidator):
    """Validates a K8s limits dictionary."""

    key_validator = K8sLimitKeyValidator
    value_validator = K8sLimitValueValidator


class K8sLabelKeyValidator(K8sAnnotationKeyValidator):
    """Validates the keys of a K8s labels dictionary."""

    error_message = "Not a valid K8s label key"


class K8sLabelsValidator(DictValidator):
    """Validates a K8s labels dictionary."""

    key_validator = K8sLabelKeyValidator
    value_validator = TypeValidator(str)


class EnvVarNameValidator(RegexValidator):
    """Validates an environment variable name."""

    regex = r"^[a-zA-Z_][a-zA-Z0-9_]*$"
    error_message = "Not a valid environment variable name"


class K8sSecretNameValidator(RegexValidator):
    """Validates the name of a K8s Secret.

    Secret names are DNS *subdomain* names (dot-separated DNS labels), unlike
    most other K8s resource names validated by `K8sNameValidator`, which are
    plain DNS *labels* and so reject dots.
    """

    _label = r"[a-z0-9]([-a-z0-9]*[a-z0-9])?"
    regex = rf"^{_label}(\.{_label})*$"
    error_message = "Not a valid K8s Secret name"


class K8sSecretKeyValidator(RegexValidator):
    """Validates a key inside a K8s Secret's data."""

    regex = r"^[-._a-zA-Z0-9]+$"
    error_message = "Not a valid K8s Secret key"


# Keys of a `{secret_name, secret_key}` mapping (see K8sSecretRefValidator),
# shared with nbprocessor.py so the two can't disagree on the dict shape.
SECRET_NAME_KEY = "secret_name"
SECRET_KEY_KEY = "secret_key"


class K8sSecretRefValidator(Validator):
    """Validates a single `{secret_name, secret_key}` mapping."""

    def _validate(self, value: dict):
        if not isinstance(value, dict) or set(value) != {
            SECRET_NAME_KEY,
            SECRET_KEY_KEY,
        }:
            raise ValueError(
                f"Secret reference must be a dict with '{SECRET_NAME_KEY}' and "
                f"'{SECRET_KEY_KEY}' keys"
            )
        K8sSecretNameValidator()(value[SECRET_NAME_KEY])
        K8sSecretKeyValidator()(value[SECRET_KEY_KEY])


class K8sSecretsValidator(DictValidator):
    """Validates a K8s secrets dictionary (env var name -> secret reference)."""

    # NOTE: instantiated (not a bare class) so the key is actually checked -
    # see DictValidator._validate, which calls key_validator(k) directly.
    key_validator = EnvVarNameValidator()
    value_validator = K8sSecretRefValidator()


class VolumeTypeValidator(EnumValidator):
    """Validates the type of a Volume."""

    enum = ("pv", "pvc", "new_pvc", "clone")


class VolumeAccessModeValidator(EnumValidator):
    """Validates the access mode of a Volume."""

    enum = ("", "rom", "rwo", "rwm")


class IsLowerValidator(Validator):
    """Validates if a string is all lowercase."""

    def _validate(self, value: str):
        return value == value.lower()


class PositiveIntegerValidator(Validator):
    """Validates a Field to be a positive integer."""

    def _validate(self, value):
        if not isinstance(value, int):
            raise ValueError(f"'{value}' is not of type 'int'")
        if value <= 0:
            raise ValueError(f"'{value}' is not a positive integer")


class OutputPathValidator(Validator):
    """Validates that an output path resolves to within the project directory."""

    def _validate(self, value: str):
        if not value:
            return
        from pathlib import Path

        project_dir = Path.cwd().resolve()
        resolved = (project_dir / value).resolve()
        if not resolved.is_relative_to(project_dir):
            raise ValueError(
                f"'{value}' is not a valid output directory. The path must be"
                " relative to the project directory (e.g. 'pipelines/output')."
            )
