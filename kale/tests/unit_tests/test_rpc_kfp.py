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

from unittest import mock

import pytest
import requests.exceptions
import urllib3.exceptions

from kale.rpc import kfp
from kale.rpc.errors import RPCServiceUnavailableError
from kale.rpc.log import KALE_LOG_FILE
from kale.rpc.run import KaleRPCRequest


@pytest.fixture
def _rpc_request():
    return KaleRPCRequest()


def _max_retry_error():
    pool = urllib3.connectionpool.HTTPConnectionPool(host="localhost", port=55555)
    return urllib3.exceptions.MaxRetryError(
        pool,
        "/apis/v2beta1/experiments",
        reason=Exception("Failed to establish a new connection: [Errno 111] Connection refused"),
    )


@pytest.mark.parametrize(
    "connection_error",
    [
        _max_retry_error(),
        requests.exceptions.ConnectionError("Connection refused"),
    ],
)
def test_list_experiments_kfp_unreachable(_rpc_request, connection_error):
    """A KFP connection failure should surface as a friendly, actionable error."""
    with (
        mock.patch("kale.rpc.kfp._get_client", side_effect=connection_error),
        pytest.raises(RPCServiceUnavailableError) as exc_info,
    ):
        kfp.list_experiments(_rpc_request)

    err = exc_info.value
    assert err.message == "KFP is not reachable."
    assert "KFP is not reachable" in err.details
    assert "compile notebooks" in err.details
    assert "upload or run pipelines" in err.details
    assert KALE_LOG_FILE in err.details
    assert err.trans_id == _rpc_request.trans_id


def test_list_experiments_kfp_unreachable_on_api_call(_rpc_request):
    """The common case: the client builds fine and the API call is what fails.

    `kfp.Client.__init__` only contacts the server when no namespace is set, and
    Kale normally has one, so `_get_client()` succeeds and the connection error
    surfaces from the API call inside the decorated function body.
    """
    client = mock.MagicMock()
    client.list_experiments.side_effect = _max_retry_error()
    with (
        mock.patch("kale.rpc.kfp._get_client", return_value=client),
        pytest.raises(RPCServiceUnavailableError),
    ):
        kfp.list_experiments(_rpc_request)


def test_get_run_kfp_unreachable(_rpc_request):
    with (
        mock.patch("kale.rpc.kfp._get_client", side_effect=_max_retry_error()),
        pytest.raises(RPCServiceUnavailableError),
    ):
        kfp.get_run(_rpc_request, "run-id")


def test_get_run_kfp_unreachable_on_api_call(_rpc_request):
    client = mock.MagicMock()
    client.get_run.side_effect = _max_retry_error()
    with (
        mock.patch("kale.rpc.kfp._get_client", return_value=client),
        pytest.raises(RPCServiceUnavailableError),
    ):
        kfp.get_run(_rpc_request, "run-id")


def test_create_experiment_kfp_unreachable(_rpc_request):
    """Connection errors raised while checking for an existing experiment propagate.

    The first `_get_client()` succeeds so that execution actually reaches the
    nested `get_experiment(request, ...)` call, which is where the failure is
    raised. This pins the `request` (not `None`) argument to that nested call:
    `get_experiment` is decorated, so passing `None` would dereference
    `None.log` and turn the connection error into an `AttributeError`.
    """
    outer_client = mock.MagicMock()
    with (
        mock.patch(
            "kale.rpc.kfp._get_client",
            side_effect=[outer_client, _max_retry_error()],
        ),
        pytest.raises(RPCServiceUnavailableError),
    ):
        kfp.create_experiment(_rpc_request, "my-experiment")


def test_create_experiment_kfp_unreachable_on_api_call(_rpc_request):
    """The existence check succeeds, then creating the experiment hits the network."""
    client = mock.MagicMock()
    client.get_experiment.side_effect = ValueError("No experiment is found with name my-experiment")
    client.create_experiment.side_effect = _max_retry_error()
    with (
        mock.patch("kale.rpc.kfp._get_client", return_value=client),
        pytest.raises(RPCServiceUnavailableError),
    ):
        kfp.create_experiment(_rpc_request, "my-experiment")


def test_list_experiments_unrelated_error_not_swallowed(_rpc_request):
    """Non-connection errors should not be turned into a service-unavailable error."""
    with (
        mock.patch("kale.rpc.kfp._get_client", side_effect=ValueError("boom")),
        pytest.raises(ValueError),
    ):
        kfp.list_experiments(_rpc_request)
