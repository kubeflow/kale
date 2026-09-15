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
    isLoadingRef,
    loadedNotebookRef,
    setIsEnabled,
    resetForNoNotebook,
  } = setters;

  const loadNotebookPanel = useCallback(
    async (notebook: NotebookPanel) => {
      if (tracker.size === 0) {
        return;
      }

      // The load sequence is async and the user may switch notebooks again
      // before it resolves. If that happens, a late-completing load must not
      // clobber the metadata of the notebook that is now active.
      const isStale = () => tracker.currentWidget !== notebook;

      // Guard persistence for the whole load: every setMetadata below reflects
      // what we read from the notebook, not a user edit, so it must not be
      // written back to the file. Cleared in the finally so it can never stay
      // stuck (e.g. on an isStale early return).
      isLoadingRef.current = true;

      try {
        const commands = new Commands(notebook, kernel);
        await notebook.sessionContext.ready;
        if (isStale()) {
          return;
        }

        // KFP UI host / custom links come from the backend and may be
        // unreachable; a failure here must not abort the metadata load.
        try {
          const [kfpUiHost, deployPanelCustomLinks] = await Promise.all([
            commands.getKfpUiHost(),
            commands.getDeployPanelCustomLinks(),
          ]);
          if (isStale()) {
            return;
          }
          const resolvedKfpUiHost = kfpUiHost || DEFAULT_UI_URL;
          setKfpUiHost(resolvedKfpUiHost);
          setDeployPanelCustomLinks(deployPanelCustomLinks);
          DeployUtils.logLinksHint(resolvedKfpUiHost, deployPanelCustomLinks);
        } catch (error) {
          if (isStale()) {
            return;
          }
          console.warn('Kale: failed to fetch KFP UI host / links', error);
          setKfpUiHost(DEFAULT_UI_URL);
        }

        const notebookMetadata = NotebookUtils.getMetaData(
          notebook,
          metadataKey,
        );

        let fetchedExperiments: IExperiment[] = [];

        if (backend) {
          // Namespace/resume-state failures (e.g. running outside a cluster)
          // must not abort the load, so the pipeline metadata still populates.
          try {
            const namespace = await commands.getNamespace();
            if (isStale()) {
              return;
            }
            setNamespace(namespace);

            const nbFilePath = getNotebookPath(notebook);
            if (nbFilePath) {
              await commands.resumeStateIfExploreNotebook(nbFilePath);
              if (isStale()) {
                return;
              }
            }
          } catch (error) {
            if (isStale()) {
              return;
            }
            console.warn(
              'Kale: failed to resolve namespace / resume state',
              error,
            );
          }

          const currentMeta = metadataRef.current;
          setGettingExperiments(true);
          // A failure fetching experiments (e.g. KFP unreachable) must not
          // abort the rest of the load: the pipeline metadata below should
          // still populate. Degrade to an empty experiment list instead.
          try {
            const expResult = await commands.getExperiments(
              currentMeta.experiment,
              currentMeta.experiment_name,
            );
            if (isStale()) {
              return;
            }
            fetchedExperiments = expResult.experiments;

            setExperiments(expResult.experiments);
            setMetadata(prev => ({
              ...prev,
              experiment: expResult.experiment,
              experiment_name: expResult.experiment_name,
            }));
          } catch (error) {
            if (isStale()) {
              return;
            }
            console.warn('Kale: failed to fetch experiments', error);
            setExperiments([]);
          }
        }

        if (notebookMetadata) {
          const currentMeta = metadataRef.current;
          const currentExperiments = experimentsRef.current;
          let experiment: IExperiment = currentMeta.experiment;
          let experiment_name: string = currentMeta.experiment_name;

          if (notebookMetadata['experiment']) {
            experiment = {
              id:
                notebookMetadata['experiment']['id'] ||
                currentMeta.experiment.id,
              name:
                notebookMetadata['experiment']['name'] ||
                currentMeta.experiment.name,
            };
            experiment_name = experiment.name;
            const experimentsToUse =
              fetchedExperiments.length > 0
                ? fetchedExperiments
                : currentExperiments;
            if (
              !experiment.id &&
              !experiment.name &&
              experimentsToUse.length > 0
            ) {
              experiment = experimentsToUse[0];
              experiment_name = experimentsToUse[0].name;
            }
          } else if (notebookMetadata['experiment_name']) {
            const matching = currentExperiments.filter(
              (e: IExperiment) =>
                e.name === notebookMetadata['experiment_name'],
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
            if (currentExperiments.length > 0) {
              experiment = currentExperiments[0];
              experiment_name = currentExperiments[0].name;
            } else if (
              currentMeta.experiment.id ||
              currentMeta.experiment.name
            ) {
              experiment = currentMeta.experiment;
              experiment_name = currentMeta.experiment_name || '';
            } else {
              experiment = { id: '', name: '' };
              experiment_name = '';
            }
          }

          const defaultPipelineName = getNotebookFileName(notebook);
          const sanitized = sanitizePipelineName(defaultPipelineName);
          setMetadata({
            ...notebookMetadata,
            experiment,
            experiment_name,
            pipeline_name:
              notebookMetadata['pipeline_name'] &&
              notebookMetadata['pipeline_name'] !== ''
                ? notebookMetadata['pipeline_name']
                : sanitized,
            pipeline_description:
              notebookMetadata['pipeline_description'] || '',
            base_image: '',
            steps_defaults: DefaultState.metadata.steps_defaults,
          });
        } else {
          const defaultPipelineName = getNotebookFileName(notebook);
          const sanitized = sanitizePipelineName(defaultPipelineName);
          setMetadata({
            ...DefaultState.metadata,
            experiment: { id: '', name: '' },
            experiment_name: '',
            pipeline_name: sanitized,
            base_image: DefaultState.metadata.base_image,
          });
        }
      } finally {
        // The load is done (or was abandoned via an isStale early return).
        // Always clear the loading state so the panel leaves "Loading..." and
        // so genuine user edits are persisted again. Only clear for the
        // notebook that is still active, to avoid a stale load re-enabling
        // persistence mid-switch.
        if (tracker.currentWidget === notebook) {
          // Mark this notebook as the owner of the current metadata BEFORE
          // re-enabling persistence, so the next user edit is written back to
          // this notebook.
          loadedNotebookRef.current = notebook;
          setGettingExperiments(false);
          isLoadingRef.current = false;
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
      isLoadingRef,
      loadedNotebookRef,
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
