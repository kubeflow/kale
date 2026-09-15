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

import { useEffect, useState } from 'react';
import { INotebookTracker, NotebookPanel } from '@jupyterlab/notebook';

/**
 * Hook that keeps the currently active notebook in React state.
 *
 * `tracker.currentWidget` is a plain JupyterLab object, so reading it while
 * rendering leaves the panel blind to notebook changes: opening a notebook
 * updates the tracker but schedules no re-render, so the panel keeps showing
 * whichever branch it last rendered.
 *
 * The panel did recover, but only as a side effect: the notebook-loading
 * sequence sets unrelated state once it finishes, and that re-render happened
 * to re-read the tracker. That sequence waits on the kernel and then on one
 * backend RPC after another, so the recovery arrives late on a slow backend
 * and never at all if a call hangs.
 *
 * Subscribing to `currentChanged` here makes the active notebook a value the
 * panel actually tracks, so it no longer depends on that timing.
 */
export function useActiveNotebook(
  tracker: INotebookTracker,
): NotebookPanel | null {
  const [activeNotebook, setActiveNotebook] = useState<NotebookPanel | null>(
    tracker.currentWidget,
  );

  useEffect(() => {
    const onCurrentChanged = (
      _tracker: INotebookTracker,
      notebook: NotebookPanel | null,
    ) => setActiveNotebook(notebook);

    // a notebook may already be open from before this mounted
    setActiveNotebook(tracker.currentWidget);
    tracker.currentChanged.connect(onCurrentChanged);

    return () => {
      tracker.currentChanged.disconnect(onCurrentChanged);
    };
  }, [tracker]);

  return activeNotebook;
}
