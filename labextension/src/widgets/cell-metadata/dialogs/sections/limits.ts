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
 * Shared by the dialog sections that edit a step's resource limits
 * (GPU, CPU, memory).
 */

export interface ILimitAction {
  action: 'update' | 'delete';
  limitKey: string;
  limitValue?: string;
}

export const limitAction = (
  action: ILimitAction['action'],
  limitKey: ILimitAction['limitKey'],
  limitValue: ILimitAction['limitValue'] = undefined,
): ILimitAction => ({ action, limitKey, limitValue });

export const GPU_TYPES = [
  { value: 'nvidia.com/gpu', label: 'Nvidia' },
  { value: 'amd.com/gpu', label: 'AMD' },
];

/** The GPU type requested in `limits`, if any. Assumes there is at most one. */
export const getGpuType = (limits: {
  [id: string]: string;
}): string | undefined =>
  Object.keys(limits).find(key => GPU_TYPES.some(t => t.value === key));

// Scoped to the limit sections: the shared Input/Select components don't have
// a dark-mode-aware disabled style, so override it here rather than in the
// shared components (which are used well beyond this dialog).
export const disabledFieldSx = {
  '& .MuiInputBase-input.Mui-disabled': {
    WebkitTextFillColor: 'var(--jp-ui-font-color2)',
  },
  '& .MuiInputLabel-root': {
    color: 'var(--jp-ui-font-color2)',
  },
  '& .MuiOutlinedInput-notchedOutline': {
    borderColor: 'var(--jp-input-border-color)',
  },
};
