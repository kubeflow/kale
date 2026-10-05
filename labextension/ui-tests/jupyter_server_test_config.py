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

"""Server configuration for integration tests.

!! Never use this configuration in production because it
opens the server to the world and provide access to JupyterLab
JavaScript objects through the global window variable.
"""

import json
from pathlib import Path
from tempfile import mkdtemp

from jupyterlab.galata import configure_jupyter_server

configure_jupyter_server(c)

# Use port 8889 to avoid conflicts with running JupyterLab instances
c.ServerApp.port = 8889

# Isolate the tests from the developer's own JupyterLab settings, and enable
# the Volumes panel (hidden by default) so the Volumes tests can reach it.
settings_dir = Path(mkdtemp(prefix="kale-ui-tests-settings-"))
kale_settings = settings_dir / "jupyterlab-kubeflow-kale" / "kale-settings.jupyterlab-settings"
kale_settings.parent.mkdir(parents=True)
kale_settings.write_text(json.dumps({"enableVolumes": True}))
c.LabApp.user_settings_dir = str(settings_dir)

# Uncomment to set server log level to debug level
# c.ServerApp.log_level = "DEBUG"
