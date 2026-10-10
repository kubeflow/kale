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

export const CELL_TYPES = [
  { value: 'imports', label: 'Imports' },
  { value: 'functions', label: 'Functions' },
  { value: 'pipeline-parameters', label: 'Pipeline Parameters' },
  { value: 'pipeline-metrics', label: 'Pipeline Metrics' },
  { value: 'step', label: 'Pipeline Step' },
  { value: 'notebook', label: 'Notebook' },
  { value: 'skip', label: 'Skip Cell' },
];

// Placed in a cell when it becomes a notebook reference: the cell names
// another notebook and holds no code of its own.
export const NOTEBOOK_REF_CELL_HINT =
  '# This cell references another notebook, so it does not run code of its own.\n' +
  '# Put the path in the Kale panel, and keep your code in a Pipeline Step cell.';

export const RESERVED_CELL_NAMES = [
  'imports',
  'functions',
  'pipeline-parameters',
  'pipeline-metrics',
  'skip',
];
export const KALE_TAG_PREFIXES = [
  'step:',
  'prev:',
  'limit:',
  'secret:',
  'image:',
  'cache:',
  'report:',
  'notebook:',
  'skip',
  'imports',
  'functions',
  'pipeline-parameters',
  'pipeline-metrics',
];

export const RESERVED_CELL_NAMES_HELP_TEXT: { [id: string]: string } = {
  imports:
    'The code in this cell will be pre-pended to every step of the pipeline.',
  functions:
    'The code in this cell will be pre-pended to every step of the pipeline,' +
    ' after `imports`.',
  'pipeline-parameters':
    'The variables in this cell will be transformed into pipeline parameters,' +
    ' preserving the current values as defaults.',
  'pipeline-metrics':
    'The variables in this cell will be transformed into pipeline metrics.',
  skip: 'This cell will be skipped and excluded from pipeline steps',
};

export const RESERVED_CELL_NAMES_CHIP_COLOR: { [id: string]: string } = {
  skip: 'a9a9a9',
  'pipeline-parameters': 'ee7a1a',
  'pipeline-metrics': '773d0d',
  imports: 'a32626',
  functions: 'a32626',
};

export const STEP_NAME_ERROR_MSG =
  "Step name must consist of lower case alphanumeric characters or '_', and can not start with a digit.";

export const NOTEBOOK_PATH_ERROR_MSG =
  'Path to a .ipynb file, relative to this notebook.';
