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

"""Constants used when processing a notebook into a pipeline.

Grouped by what each string actually *is*, since they are not
interchangeable: keys read from the notebook JSON, the cell tag language,
the keys of the parsed-tag dictionary shared between
``parse_cell_metadata`` and ``parse_notebook``, names of
:class:`~kale.step.Step` attributes looked up dynamically, and code
templates / type maps.
"""

from kale.config import validators


def _regex_body(pattern: str) -> str:
    """Strip the `^`/`$` anchors so a validator regex can be nested inside a larger one."""
    return pattern.removeprefix("^").removesuffix("$")


# --------------------------------------------------------------------------
# Notebook JSON keys and the cell tag language
# --------------------------------------------------------------------------

# fixme: Change the name of this key to `kale_metadata`
KALE_NB_METADATA_KEY = "kubeflow_notebook"

SKIP_TAG = r"^skip$"
IMPORT_TAG = r"^imports$"
FUNCTIONS_TAG = r"^functions$"
PREV_TAG = r"^prev:[_a-z]([_a-z0-9]*)?$"
STEP_TAG = r"^step:([_a-z]([_a-z0-9]*)?)?$"
# A `notebook:<name>` cell references another notebook as a sub-pipeline. The
# referenced path is carried in the cell metadata (`notebook_path`), not the tag.
NOTEBOOK_TAG = r"^notebook:([_a-z]([_a-z0-9]*)?)?$"
PIPELINE_PARAMETERS_TAG = r"^pipeline-parameters$"
PIPELINE_METRICS_TAG = r"^pipeline-metrics$"
# Annotations map to actual pod annotations that can be set via KFP SDK
_segment = "[a-zA-Z0-9]+([a-zA-Z0-9-_.]*[a-zA-Z0-9])?"
K8S_ANNOTATION_KEY = f"{_segment}([/]{_segment})?"
ANNOTATION_TAG = rf"^annotation:{K8S_ANNOTATION_KEY}:(.*)$"
LABEL_TAG = rf"^label:{K8S_ANNOTATION_KEY}:(.*)$"
# Limits map to K8s limits, like CPU, Mem, GPU, ...
# E.g.: limit:nvidia.com/gpu:2
LIMITS_TAG = r"^limit:([_a-z-\.\/]+):([_a-zA-Z0-9\.]+)$"
# Secrets map a K8s Secret's key to an env var, injected via
# kfp.kubernetes.use_secret_as_env. Built from the same validators applied to
# StepConfig.secrets (see K8sSecretsValidator) so the two can't drift apart.
# E.g.: secret:db-credentials:password:DB_PASSWORD
# The tag prefix, i.e. the first `:`-separated part of a `secret:...` tag.
SECRET_CONF_TYPE = "secret"
SECRET_TAG = (
    r"^secret:"
    rf"({_regex_body(validators.K8sSecretNameValidator.regex)}):"
    rf"({_regex_body(validators.K8sSecretKeyValidator.regex)}):"
    rf"({_regex_body(validators.EnvVarNameValidator.regex)})$"
)
# Image tag for per-step Base image selection
# E.g.: image:python:3.11-slim
IMAGE_TAG = r"^image:(.+)$"
# Cache tag for per-step caching control
# E.g.: cache:enabled or cache:disabled
CACHE_ENABLED = "enabled"
CACHE_DISABLED = "disabled"
CACHE_TAG = rf"^cache:({CACHE_ENABLED}|{CACHE_DISABLED})$"
# Report tag for per-step HTML report generation control
# E.g.: report:enabled or report:disabled
REPORT_ENABLED = "enabled"
REPORT_DISABLED = "disabled"
REPORT_TAG = rf"^report:({REPORT_ENABLED}|{REPORT_DISABLED})$"

TAGS_LANGUAGE = [
    SKIP_TAG,
    IMPORT_TAG,
    FUNCTIONS_TAG,
    PREV_TAG,
    STEP_TAG,
    NOTEBOOK_TAG,
    PIPELINE_PARAMETERS_TAG,
    PIPELINE_METRICS_TAG,
    ANNOTATION_TAG,
    LABEL_TAG,
    LIMITS_TAG,
    SECRET_TAG,
    IMAGE_TAG,
    CACHE_TAG,
    REPORT_TAG,
]
# These tags are applied to every step of the pipeline
STEPS_DEFAULTS_LANGUAGE = [
    ANNOTATION_TAG,
    LABEL_TAG,
    LIMITS_TAG,
    SECRET_TAG,
    IMAGE_TAG,
    CACHE_TAG,
    REPORT_TAG,
]


METRICS_TEMPLATE = """\
from kale.common import kfputils as _kale_kfputils
_kale_kfp_metrics = {
%s
}
_kale_kfputils.generate_mlpipeline_metrics(_kale_kfp_metrics)\
"""

KFP_ARTIFACT_TYPE_MAP = {
    "model": "Model",  # if "model" in var_name.lower()-> kfp.dsl.Model
    "dataset": "Dataset",  # if "dataset" in var_name.lower()-> kfp.dsl.Dataset
    "data": "Dataset",  # if "data" in var_name.lower()-> kfp.dsl.Dataset
    "metrics": "Metrics",  # if "metrics" in var_name.lower()-> kfp.dsl.Metrics
    "classification": "ClassificationMetrics",
    r"a-zA-Z0-9_": "Artifact",  # default for any other variable
}


# Separator between a tag's parts, e.g. `limit:nvidia.com/gpu:2`.
TAG_SEPARATOR = ":"

# Cell-level metadata key holding the list of Kale tags.
CELL_METADATA_TAGS = "tags"

# `cell_type` value for cells Kale can turn into pipeline code.
CELL_TYPE_CODE = "code"


# --------------------------------------------------------------------------
# Parsed-tag dictionary keys
#
# `parse_cell_metadata` produces this dict and `parse_notebook` consumes it,
# so both sides must agree on every key.
# --------------------------------------------------------------------------

STEP_NAMES = "step_names"
PREV_STEPS = "prev_steps"
NOTEBOOK_NAMES = "notebook_names"
# Carried from the referencing cell's metadata into the parsed tags under
# the same name, so it serves both.
NOTEBOOK_PATH = "notebook_path"
ANNOTATIONS = "annotations"
LABELS = "labels"
LIMITS = "limits"
SECRETS = "secrets"
BASE_IMAGE = "base_image"
ENABLE_CACHING = "enable_caching"
GENERATE_HTML_REPORT = "generate_html_report"

# Field name of the pipeline-level defaults on `NotebookConfig`.
STEPS_DEFAULTS = "steps_defaults"


# --------------------------------------------------------------------------
# Dynamically accessed Step attributes
#
# Looked up with getattr/hasattr, so a typo silently degrades to None
# instead of raising.
# --------------------------------------------------------------------------

FNS_FREE_VARIABLES = "fns_free_variables"
PARAMETERS = "parameters"


# --------------------------------------------------------------------------
# Default inferred types
# --------------------------------------------------------------------------

DEFAULT_VARIABLE_TYPE = "str"
DEFAULT_ARTIFACT_TYPE = "Artifact"
