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

import type { NotebookPanel } from '@jupyterlab/notebook';
import { resolveMetadataPersistence } from '../widgets/hooks/metadataPersistenceDecision';

// Minimal NotebookPanel stub: the decision only reads `isDisposed` and uses
// object identity to distinguish notebooks.
function makeNotebook(isDisposed = false): NotebookPanel {
  return { isDisposed } as unknown as NotebookPanel;
}

describe('resolveMetadataPersistence (#644 regression)', () => {
  it('writes changed metadata to the owning notebook', () => {
    const owner = makeNotebook();
    const decision = resolveMetadataPersistence({
      json: '{"pipeline_name":"a"}',
      prevJson: '{"pipeline_name":""}',
      isLoading: false,
      loadedNotebook: owner,
    });
    expect(decision.shouldWrite).toBe(true);
    expect(decision.target).toBe(owner);
  });

  it('targets the owning notebook, not the currently active tab', () => {
    // This is the core of the #644 leak: the effect runs after a paint, and by
    // then the active tab may be a different notebook. The write must still go
    // to the notebook the metadata was loaded from.
    const owningNotebook = makeNotebook();
    const nowActiveNotebook = makeNotebook();

    const decision = resolveMetadataPersistence({
      json: '{"pipeline_name":"belongs-to-owner"}',
      prevJson: '{"pipeline_name":""}',
      isLoading: false,
      loadedNotebook: owningNotebook,
    });

    expect(decision.shouldWrite).toBe(true);
    expect(decision.target).toBe(owningNotebook);
    // Never the active tab.
    expect(decision.target).not.toBe(nowActiveNotebook);
  });

  it('does not write while the loader is populating state', () => {
    const owner = makeNotebook();
    const decision = resolveMetadataPersistence({
      json: '{"pipeline_name":"a"}',
      prevJson: '{"pipeline_name":""}',
      isLoading: true,
      loadedNotebook: owner,
    });
    expect(decision.shouldWrite).toBe(false);
    expect(decision.target).toBeNull();
  });

  it('does not write when metadata is unchanged', () => {
    const owner = makeNotebook();
    const sameJson = '{"pipeline_name":"a"}';
    const decision = resolveMetadataPersistence({
      json: sameJson,
      prevJson: sameJson,
      isLoading: false,
      loadedNotebook: owner,
    });
    expect(decision.shouldWrite).toBe(false);
  });

  it('does not write when there is no owning notebook', () => {
    const decision = resolveMetadataPersistence({
      json: '{"pipeline_name":"a"}',
      prevJson: '{"pipeline_name":""}',
      isLoading: false,
      loadedNotebook: null,
    });
    expect(decision.shouldWrite).toBe(false);
    expect(decision.target).toBeNull();
  });

  it('does not write when the owning notebook has been disposed', () => {
    const disposed = makeNotebook(true);
    const decision = resolveMetadataPersistence({
      json: '{"pipeline_name":"a"}',
      prevJson: '{"pipeline_name":""}',
      isLoading: false,
      loadedNotebook: disposed,
    });
    expect(decision.shouldWrite).toBe(false);
  });
});
