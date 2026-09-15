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

import { MutableRefObject, useEffect, useRef } from 'react';
import { NotebookPanel } from '@jupyterlab/notebook';
import NotebookUtils from '../../lib/NotebookUtils';
import { IKaleNotebookMetadata } from '../LeftPanelTypes';
import { resolveMetadataPersistence } from './metadataPersistenceDecision';

interface IUseNotebookMetadataPersistenceParams {
  metadata: IKaleNotebookMetadata;
  metadataKey: string;
  // Set while the loader is populating state from a notebook. Metadata changes
  // during that window are programmatic (a reflection of what was read), not
  // user edits, so they must not be written back to the notebook file.
  isLoadingRef: MutableRefObject<boolean>;
  // Identifies the notebook the current metadata state belongs to. The write
  // targets this notebook, NOT tracker.currentWidget: the persistence effect
  // runs asynchronously (after paint), so by the time it runs the user may
  // have switched tabs and tracker.currentWidget may point at a different
  // notebook. Writing to currentWidget would leak one notebook's metadata into
  // another. Writing to the owning notebook keeps each notebook's data with it.
  loadedNotebookRef: MutableRefObject<NotebookPanel | null>;
}

/**
 * Hook that writes the current metadata state back to its owning notebook's
 * .ipynb file whenever it changes, keeping the form and the file in sync.
 */
export function useNotebookMetadataPersistence({
  metadata,
  metadataKey,
  isLoadingRef,
  loadedNotebookRef,
}: IUseNotebookMetadataPersistenceParams) {
  const prevMetadataJsonRef = useRef(JSON.stringify(metadata));

  useEffect(() => {
    const json = JSON.stringify(metadata);
    const decision = resolveMetadataPersistence({
      json,
      prevJson: prevMetadataJsonRef.current,
      isLoading: isLoadingRef.current,
      loadedNotebook: loadedNotebookRef.current,
    });
    // Always track the latest metadata we have seen (even when we skip the
    // write) so that, once loading finishes, the next genuine user edit is
    // detected as a change.
    prevMetadataJsonRef.current = json;
    if (decision.shouldWrite && decision.target) {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { base_image: _baseImage, ...metadataToPersist } = metadata;
      NotebookUtils.setMetaData(
        decision.target,
        metadataKey,
        metadataToPersist,
      );
    }
  }, [metadata, metadataKey, isLoadingRef, loadedNotebookRef]);
}
