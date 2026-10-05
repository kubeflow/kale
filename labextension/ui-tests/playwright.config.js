// Copyright 2026 The Kubeflow Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * Configuration for Playwright using default from @jupyterlab/galata
 */
const baseConfig = require('@jupyterlab/galata/lib/playwright-config');

module.exports = {
  ...baseConfig,
  // Every test shares a single JupyterLab server, so run them one at a time
  workers: 1,
  // Absorb occasional timing flakes on slow CI runners
  retries: process.env.CI ? 2 : 0,
  timeout: 120 * 1000,
  use: {
    ...baseConfig.use,
    baseURL: 'http://localhost:8889',
  },
  webServer: {
    command: 'jlpm start',
    url: 'http://localhost:8889/lab',
    timeout: 120 * 1000,
    reuseExistingServer: !process.env.CI,
  },
};
