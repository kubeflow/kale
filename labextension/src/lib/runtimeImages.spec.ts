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

import {
  getRuntimeImageName,
  migrateRuntimeImages,
  migrateRuntimeImageSettingsRaw,
  repairRuntimeImageTag,
} from './runtimeImages';

describe('runtime image settings migration', () => {
  it('keeps image references as names and values', () => {
    expect(
      migrateRuntimeImages(['python:3.12', 'registry/image@sha256:abc']),
    ).toEqual({
      'python:3.12': 'python:3.12',
      'registry/image@sha256:abc': 'registry/image@sha256:abc',
    });
  });

  it('handles duplicates, blank entries, and object-prototype keys', () => {
    const migrated = migrateRuntimeImages([
      'python:3.12',
      'python:3.12',
      '',
      '__proto__',
    ]);
    expect(migrated?.['python:3.12']).toBe('python:3.12');
    expect(migrated?.['__proto__']).toBe('__proto__');
    expect(Object.keys(migrated ?? {})).toHaveLength(2);
  });

  it('leaves the new dictionary format alone', () => {
    expect(migrateRuntimeImages({ Python: 'python:3.12' })).toBeNull();
  });

  it('rewrites JSON5 user settings and preserves other settings', () => {
    const migrated = migrateRuntimeImageSettingsRaw(`{
      // User preference
      enableKaleByDefault: true,
      runtimeImages: ['registry/image@sha256:abc',],
    }`);
    expect(JSON.parse(migrated?.raw ?? '{}')).toEqual({
      enableKaleByDefault: true,
      runtimeImages: {
        'registry/image@sha256:abc': 'registry/image@sha256:abc',
      },
    });
    expect(
      migrateRuntimeImageSettingsRaw(
        '{runtimeImages: {Python: "python:3.12"}}',
      ),
    ).toBeNull();
  });
});

describe('runtime image display name', () => {
  it('finds the name for a stored image reference', () => {
    const images = { Training: 'registry/image@sha256:abc' };
    expect(getRuntimeImageName(images, 'registry/image@sha256:abc')).toBe(
      'Training',
    );
    expect(getRuntimeImageName(images, 'custom/image:1')).toBeUndefined();
  });

  it('repairs a display name saved as an image tag without changing other tags', () => {
    const images = {
      'PyTorch 2.0': 'pytorch/pytorch:2.0',
    };
    expect(
      repairRuntimeImageTag(['step:train', 'image:PyTorch 2.0'], images),
    ).toEqual(['step:train', 'image:pytorch/pytorch:2.0']);
    expect(
      repairRuntimeImageTag(
        ['step:train', 'image:pytorch/pytorch:2.0'],
        images,
      ),
    ).toBeNull();
    expect(repairRuntimeImageTag(['image:custom/image:1'], images)).toBeNull();
  });
});
