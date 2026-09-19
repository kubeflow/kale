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

import { useCallback, useEffect } from 'react';
import { INotebookTracker, NotebookPanel } from '@jupyterlab/notebook';
import { Kernel } from '@jupyterlab/services';
import { PageConfig } from '@jupyterlab/coreutils';
import NotebookUtils from '../../lib/NotebookUtils';
import Commands from '../../lib/Commands';
import { DefaultState, IExperiment, NEW_EXPERIMENT } from '../LeftPanelTypes';
import { ILoaderSetters } from './useNotebookMetadata';
import DeployUtils from '../deploys-progress/DeployUtils';

const DEFAULT_UI_URL = 'http://localhost:8080';

function getNotebookFileName(notebook: NotebookPanel | null): string {
  if (!notebook?.context?.path) {
    return '';
  }
  const path = notebook.context.path as string;
  const base = path.split('/').pop() || '';
  return base.replace(/\.ipynb$/i, '');
}

function sanitizePipelineName(name: string): string {
  if (!name) {
    return '';
  }
  let s = name.toLowerCase();
  s = s.replace(/[^a-z0-9-]+/g, '-');
  s = s.replace(/-+/g, '-');
  s = s.replace(/^-+|-+$/g, '');
  if (!/^[a-z0-9].*[a-z0-9]$/.test(s)) {
    return 'pipeline-' + Date.now().toString(36);
  }
  return s;
}

function getNotebookPath(notebook: NotebookPanel | null): string | false {
  if (!notebook) {
    return false;
  }
  return PageConfig.getOption('serverRoot') + '/' + notebook.context.path;
}

interface IUseNotebookLoaderParams {
  tracker: INotebookTracker;
  backend: boolean;
  kernel: Kernel.IKernelConnection;
  enableKaleByDefault: boolean;
  metadataKey: string;
  setters: ILoaderSetters;
}

/**
 * Hook that wires up to the notebook tracker's currentChanged signal and
 * runs the async notebook-loading sequence (session ready, backend RPCs,
 * metadata read/merge) whenever the active notebook changes.
 */
export function useNotebookLoader({
  tracker,
  backend,
  kernel,
  enableKaleByDefault,
  metadataKey,
  setters,
}: IUseNotebookLoaderParams) {
  const {
    setKfpUiHost,
    setDeployPanelCustomLinks,
    setNamespace,
    setGettingExperiments,
    metadataRef,
    setExperiments,
    setMetadata,
    experimentsRef,
    setIsEnabled,
    resetForNoNotebook,
  } = setters;

  // Apply the notebook's saved Kale metadata to the panel. `availableExperiments`
  // is whatever experiment list is currently known (empty when KFP has not
  // loaded yet); it is only used to pick a sensible default experiment when the
  // saved metadata doesn't fully specify one. This does not touch KFP, so it can
  // (and must) run before any KFP call.
  const applySavedMetadata = useCallback(
    (
      notebook: NotebookPanel,
      notebookMetadata: Record<string, any> | null,
      availableExperiments: IExperiment[],
    ) => {
      const defaultPipelineName = getNotebookFileName(notebook);
      const sanitized = sanitizePipelineName(defaultPipelineName);

      if (!notebookMetadata) {
        setMetadata(prev => ({
          ...DefaultState.metadata,
          experiment: prev.experiment,
          experiment_name: prev.experiment_name,
          pipeline_name: sanitized,
          base_image: DefaultState.metadata.base_image,
        }));
        return;
      }

      const currentMeta = metadataRef.current;
      let experiment: IExperiment = currentMeta.experiment;
      let experiment_name: string = currentMeta.experiment_name;

      if (notebookMetadata['experiment']) {
        experiment = {
          id: notebookMetadata['experiment']['id'] || currentMeta.experiment.id,
          name:
            notebookMetadata['experiment']['name'] ||
            currentMeta.experiment.name,
        };
        experiment_name = experiment.name;
        if (
          !experiment.id &&
          !experiment.name &&
          availableExperiments.length > 0
        ) {
          experiment = availableExperiments[0];
          experiment_name = availableExperiments[0].name;
        }
      } else if (notebookMetadata['experiment_name']) {
        const matching = availableExperiments.filter(
          (e: IExperiment) => e.name === notebookMetadata['experiment_name'],
        );
        if (matching.length > 0) {
          experiment = matching[0];
        } else {
          experiment = {
            id: NEW_EXPERIMENT.id,
            name: notebookMetadata['experiment_name'],
          };
        }
        experiment_name = notebookMetadata['experiment_name'];
      } else {
        if (availableExperiments.length > 0) {
          experiment = availableExperiments[0];
          experiment_name = availableExperiments[0].name;
        } else if (currentMeta.experiment.id || currentMeta.experiment.name) {
          experiment = currentMeta.experiment;
          experiment_name = currentMeta.experiment_name || '';
        } else {
          experiment = { id: '', name: '' };
          experiment_name = '';
        }
      }

      setMetadata({
        ...notebookMetadata,
        experiment,
        experiment_name,
        pipeline_name:
          notebookMetadata['pipeline_name'] &&
          notebookMetadata['pipeline_name'] !== ''
            ? notebookMetadata['pipeline_name']
            : sanitized,
        pipeline_description: notebookMetadata['pipeline_description'] || '',
        base_image: '',
        steps_defaults: DefaultState.metadata.steps_defaults,
      });
    },
    [setMetadata, metadataRef],
  );

  const loadNotebookPanel = useCallback(
    async (notebook: NotebookPanel) => {
      if (tracker.size === 0) {
        return;
      }

      const commands = new Commands(notebook, kernel);
      await notebook.sessionContext.ready;

      const [kfpUiHost, deployPanelCustomLinks] = await Promise.all([
        commands.getKfpUiHost(),
        commands.getDeployPanelCustomLinks(),
      ]);
      const resolvedKfpUiHost = kfpUiHost || DEFAULT_UI_URL;
      setKfpUiHost(resolvedKfpUiHost);
      setDeployPanelCustomLinks(deployPanelCustomLinks);
      DeployUtils.logLinksHint(resolvedKfpUiHost, deployPanelCustomLinks);

      const notebookMetadata = NotebookUtils.getMetaData(notebook, metadataKey);

      // Apply the notebook's saved metadata (pipeline name, description,
      // experiment) to the panel FIRST, before any KFP call. This metadata is
      // stored in the notebook file and is independent of KFP, so it must be
      // shown immediately regardless of KFP state (loading, disconnected, or
      // connected). Previously it was applied only after awaiting getExperiments,
      // which left the fields blank while KFP was loading or unreachable (#965).
      applySavedMetadata(notebook, notebookMetadata, experimentsRef.current);

      if (backend) {
        setNamespace(await commands.getNamespace());

        const nbFilePath = getNotebookPath(notebook);
        if (nbFilePath) {
          await commands.resumeStateIfExploreNotebook(nbFilePath);
        }

        setGettingExperiments(true);
        // Fetching experiments requires KFP. If KFP is disconnected or still
        // loading this rejects; the saved metadata is already shown, so we just
        // skip enriching the experiment list. On success we refresh the
        // experiment list and re-resolve the selected experiment against it.
        try {
          const currentMeta = metadataRef.current;
          const expResult = await commands.getExperiments(
            currentMeta.experiment,
            currentMeta.experiment_name,
          );
          setExperiments(expResult.experiments);
          setMetadata(prev => ({
            ...prev,
            experiment: expResult.experiment,
            experiment_name: expResult.experiment_name,
          }));
        } catch (error) {
          console.warn(
            'Kale: could not fetch experiments (KFP may be unreachable); ' +
              'notebook metadata is shown without the experiment list.',
            error,
          );
          setExperiments([]);
        } finally {
          setGettingExperiments(false);
        }
      }
    },
    [
      tracker,
      backend,
      kernel,
      metadataKey,
      setKfpUiHost,
      setDeployPanelCustomLinks,
      setNamespace,
      setGettingExperiments,
      metadataRef,
      setExperiments,
      setMetadata,
      experimentsRef,
      applySavedMetadata,
    ],
  );

  useEffect(() => {
    const handleNotebookChanged = async (
      _tracker: INotebookTracker,
      notebook: NotebookPanel | null,
    ) => {
      if (notebook) {
        await loadNotebookPanel(notebook);
        setIsEnabled(prev => enableKaleByDefault || prev);
      } else {
        resetForNoNotebook();
      }
    };

    tracker.currentChanged.connect(handleNotebookChanged);

    if (tracker.currentWidget instanceof NotebookPanel) {
      loadNotebookPanel(tracker.currentWidget);
    }

    return () => {
      tracker.currentChanged.disconnect(handleNotebookChanged);
    };
  }, [
    tracker,
    loadNotebookPanel,
    enableKaleByDefault,
    setIsEnabled,
    resetForNoNotebook,
  ]);
}
