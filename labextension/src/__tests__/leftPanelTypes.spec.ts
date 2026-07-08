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

import { createDefaultMetadata, DefaultState } from '../widgets/LeftPanelTypes';

// Regression tests for https://github.com/kubeflow/kale/issues/643:
// notebook state must never share object references with the DefaultState
// global, otherwise an in-place write leaks into every open notebook.
describe('createDefaultMetadata', () => {
  it('returns a fresh metadata object on every call', () => {
    const first = createDefaultMetadata();
    const second = createDefaultMetadata();
    expect(first).not.toBe(second);
    expect(first).toEqual(second);
  });

  it('returns fresh nested objects and arrays on every call', () => {
    const first = createDefaultMetadata();
    const second = createDefaultMetadata();
    expect(first.experiment).not.toBe(second.experiment);
    expect(first.volumes).not.toBe(second.volumes);
    expect(first.steps_defaults).not.toBe(second.steps_defaults);
  });

  it('does not share references with DefaultState.metadata', () => {
    const metadata = createDefaultMetadata();
    expect(metadata).not.toBe(DefaultState.metadata);
    expect(metadata.experiment).not.toBe(DefaultState.metadata.experiment);
    expect(metadata.volumes).not.toBe(DefaultState.metadata.volumes);
    expect(metadata.steps_defaults).not.toBe(
      DefaultState.metadata.steps_defaults,
    );
  });

  it('produces objects that are safe to mutate without affecting defaults', () => {
    const metadata = createDefaultMetadata();
    metadata.pipeline_description = 'mutated';
    metadata.volumes!.push({ name: 'pvc', mount_point: '/data', type: 'pvc' });
    metadata.steps_defaults!.push('label:mutated');
    const fresh = createDefaultMetadata();
    expect(fresh.pipeline_description).toBe('');
    expect(fresh.volumes).toEqual([]);
    expect(fresh.steps_defaults).toEqual([]);
  });
});

describe('DefaultState', () => {
  it('is deep-frozen so in-place writes cannot leak between notebooks', () => {
    expect(Object.isFrozen(DefaultState)).toBe(true);
    expect(Object.isFrozen(DefaultState.metadata)).toBe(true);
    expect(Object.isFrozen(DefaultState.metadata.experiment)).toBe(true);
    expect(Object.isFrozen(DefaultState.metadata.volumes)).toBe(true);
    expect(Object.isFrozen(DefaultState.metadata.steps_defaults)).toBe(true);
  });

  it('throws on in-place writes instead of leaking them', () => {
    expect(() => {
      (
        DefaultState.metadata as { pipeline_description: string }
      ).pipeline_description = 'leaked';
    }).toThrow(TypeError);
    expect(() =>
      DefaultState.metadata.volumes!.push({
        name: 'pvc',
        mount_point: '/data',
        type: 'pvc',
      }),
    ).toThrow(TypeError);
  });

  it('keeps the documented default values', () => {
    expect(DefaultState.metadata).toEqual(createDefaultMetadata());
  });
});
