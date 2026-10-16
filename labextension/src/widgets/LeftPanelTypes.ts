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

export type DeployType = 'compile' | 'run' | 'upload';

export const PIPELINE_NAME_MAX_LENGTH = 124;

export interface IExperiment {
  id: string;
  name: string;
}

export interface IDeployPanelCustomLinks {
  upload: string;
  run: string;
}

export const NEW_EXPERIMENT: IExperiment = {
  name: '+ New Experiment',
  id: 'new',
};

// Security context settings for pipeline steps
// Uses Python naming convention as it will be read by Kale backend
export interface ISecurityContext {
  enabled?: boolean;
  run_as_user?: number;
  run_as_group?: number;
  run_as_non_root?: boolean;
}

export interface IVolumeConfig {
  name: string;
  mount_point: string;
  type: 'pvc';
  expose_as_env_var?: boolean;
}

// keep names with Python notation because they will be read
// in python by Kale.
export interface IKaleNotebookMetadata {
  experiment: IExperiment;
  experiment_name: string; // Keep this for backwards compatibility
  pipeline_name: string;
  pipeline_description: string;
  base_image: string;
  enable_caching?: boolean;

  volumes?: IVolumeConfig[];
  steps_defaults?: string[];
  storage_class_name?: string;
  security_context?: ISecurityContext;
  output_path?: string;
}

// Every consumer must get its own copy: sharing one mutable object between
// the React state of different notebooks leaks values across them (#643).
export function createDefaultMetadata(): IKaleNotebookMetadata {
  return {
    experiment: { id: '', name: '' },
    experiment_name: '',
    pipeline_name: '',
    pipeline_description: '',
    base_image: '',
    enable_caching: true,
    volumes: [],
    steps_defaults: [],
  };
}

function freezeMetadata(
  metadata: IKaleNotebookMetadata,
): Readonly<IKaleNotebookMetadata> {
  Object.freeze(metadata.experiment);
  if (metadata.volumes) {
    Object.freeze(metadata.volumes);
  }
  if (metadata.steps_defaults) {
    Object.freeze(metadata.steps_defaults);
  }
  return Object.freeze(metadata);
}

// Frozen so an accidental in-place write throws instead of silently
// leaking into every open notebook.
export const DefaultState = Object.freeze({
  metadata: freezeMetadata(createDefaultMetadata()),
});
