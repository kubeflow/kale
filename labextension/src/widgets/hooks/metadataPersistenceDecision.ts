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

export interface IPersistenceDecisionInput {
  // JSON of the metadata about to be considered for persistence.
  json: string;
  // JSON of the metadata last seen by the effect (change detection).
  prevJson: string;
  // Whether the loader is currently populating metadata state.
  isLoading: boolean;
  // The notebook the current metadata belongs to (write target), or null.
  loadedNotebook: NotebookPanel | null;
}

export interface IPersistenceDecision {
  // Whether to write the metadata back to the notebook file.
  shouldWrite: boolean;
  // The notebook to write to, if shouldWrite is true.
  target: NotebookPanel | null;
}

/**
 * Pure decision for whether the current metadata should be written back to a
 * notebook, and to which notebook.
 *
 * The critical rule (regression guard for #644): the write target is the
 * notebook the metadata was loaded from (`loadedNotebook`), never the currently
 * active tab. The persistence effect runs asynchronously after a paint, so by
 * the time it runs the active tab may already be a different notebook; writing
 * to the active tab would leak one notebook's metadata into another.
 *
 * Kept free of runtime imports so it can be unit-tested without pulling in the
 * JupyterLab module graph.
 */
export function resolveMetadataPersistence({
  json,
  prevJson,
  isLoading,
  loadedNotebook,
}: IPersistenceDecisionInput): IPersistenceDecision {
  // Unchanged metadata: nothing to persist.
  if (json === prevJson) {
    return { shouldWrite: false, target: null };
  }
  // Loader is populating state: these are reads, not user edits.
  if (isLoading) {
    return { shouldWrite: false, target: null };
  }
  // No owning notebook, or it has been closed: nowhere to write.
  if (!loadedNotebook || loadedNotebook.isDisposed) {
    return { shouldWrite: false, target: null };
  }
  return { shouldWrite: true, target: loadedNotebook };
}
