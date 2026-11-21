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

// NOTE: These strings are duplicated in the backend (kale/compiler.py).
// In the future, both sides should use a shared JSON
export const PVC_ACCESS_MODE_RWO = 'ReadWriteOnce';
export const PVC_ACCESS_MODE_RWOP = 'ReadWriteOncePod';

/** Derive KALE_VOLUME_<SCREAMING_SNAKE_CASE> from a PVC name. */
export function deriveEnvVarName(pvcName: string): string {
  return 'KALE_VOLUME_' + pvcName.toUpperCase().replace(/[^A-Z0-9]/g, '_');
}

// Portable Filename Character Set (POSIX.1-2017, 3.282): letters, digits,
// '.', '_' and '-'. Applied per path segment below.
const POSIX_PATH_SEGMENT_REGEX = /^[A-Za-z0-9._-]+$/;

/**
 * Validate a mount path against the POSIX portable path rules: must be an
 * absolute path, contain no whitespace, and have no "." / ".." segments
 * (which could be used for path traversal).
 *
 * Returns an error message if invalid, or `null` if the path is valid (an
 * empty/blank path is treated as valid here — required-field checks are the
 * caller's responsibility).
 */
export function getMountPathError(path: string): string | null {
  const trimmed = path.trim();
  if (trimmed === '') {
    return null;
  }
  if (!trimmed.startsWith('/')) {
    return 'Mount path must be an absolute path starting with "/"';
  }
  if (trimmed !== '/' && trimmed.endsWith('/')) {
    return 'Mount path must not end with "/"';
  }
  const segments = trimmed.split('/').filter(s => s !== '');
  for (const segment of segments) {
    if (segment === '.' || segment === '..') {
      return 'Mount path must not contain "." or ".." segments';
    }
    if (!POSIX_PATH_SEGMENT_REGEX.test(segment)) {
      return 'Mount path may only contain letters, numbers, ".", "_" and "-" in each segment';
    }
  }
  return null;
}

export interface IAddFormState {
  name: string;
  mount_point: string;
  expose_as_env_var: boolean;
}

export const EMPTY_FORM: IAddFormState = {
  name: '',
  mount_point: '',
  expose_as_env_var: false,
};

export interface INotebookVolume {
  name: string;
  mount_point: string;
  access_modes?: string[];
}

export interface IPvcInfo {
  name: string;
  access_modes: string[];
}

/** Format access modes for display (e.g., "RWO" for ReadWriteOnce). */
export function formatAccessModes(modes: string[] | undefined): string {
  if (!modes || modes.length === 0) {
    return '';
  }
  const abbrevMap: Record<string, string> = {
    ReadWriteOnce: 'RWO',
    ReadOnlyMany: 'ROX',
    ReadWriteMany: 'RWX',
    ReadWriteOncePod: 'RWOP',
  };
  return modes.map(m => abbrevMap[m] || m).join(', ');
}

/**
 * Check if access modes indicate a restricted volume (RWO or RWOP).
 * - ReadWriteOnce (RWO): can only be mounted by pods on the same node
 * - ReadWriteOncePod (RWOP): can only be mounted by a single pod
 * Both can cause issues when pipeline steps run in parallel.
 */
export function isRestrictedAccessMode(modes: string[] | undefined): boolean {
  if (!modes || modes.length === 0) {
    return false;
  }
  return modes.some(
    m => m === PVC_ACCESS_MODE_RWO || m === PVC_ACCESS_MODE_RWOP,
  );
}
