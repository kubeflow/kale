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
  isEnabled: boolean;
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
  isEnabled,
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
    isEnabledRef,
    resetForNoNotebook,
  } = setters;

  // Apply the notebook's saved Kale metadata (pipeline name, description,
  // experiment) to the panel. `availableExperiments` is whatever experiment
  // list is currently known (empty when KFP has not loaded or is disconnected);
  // it is only used to pick a sensible default experiment when the saved
  // metadata doesn't fully specify one. This does not touch KFP, so it can (and
  // must) run before any KFP call so the fields fill in regardless of KFP state
  // (#965).
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

  const fetchExperiments = useCallback(
    async (notebook: NotebookPanel): Promise<IExperiment[]> => {
      const commands = new Commands(notebook, kernel);
      await notebook.sessionContext.ready;
      try {
        setNamespace(await commands.getNamespace());
      } catch (error) {
        console.error('Failed to get namespace:', error);
      }
      setGettingExperiments(true);
      const currentMeta = metadataRef.current;
      const expResult = await commands.getExperiments(
        currentMeta.experiment,
        currentMeta.experiment_name,
      );
      setExperiments(expResult.experiments);
      setGettingExperiments(false);
      setMetadata(prev => ({
        ...prev,
        experiment: expResult.experiment,
        experiment_name: expResult.experiment_name,
      }));
      return expResult.experiments;
    },
    [
      kernel,
      metadataRef,
      setExperiments,
      setGettingExperiments,
      setMetadata,
      setNamespace,
    ],
  );
  const loadNotebookPanel = useCallback(
    async (notebook: NotebookPanel) => {
      if (tracker.size === 0) {
        return;
      }
      const commands = new Commands(notebook, kernel);
      await notebook.sessionContext.ready;

      // Apply the notebook's saved metadata to the panel FIRST, before ANY KFP
      // call (including getKfpUiHost below). This metadata lives in the notebook
      // file and is independent of KFP, so the fields must fill in immediately
      // regardless of KFP state — loading, disconnected, or connected (#965).
      const notebookMetadata = NotebookUtils.getMetaData(notebook, metadataKey);
      applySavedMetadata(notebook, notebookMetadata, experimentsRef.current);

      const [kfpUiHost, deployPanelCustomLinks] = await Promise.all([
        commands.getKfpUiHost(),
        commands.getDeployPanelCustomLinks(),
      ]);
      const resolvedKfpUiHost = kfpUiHost || DEFAULT_UI_URL;
      setKfpUiHost(resolvedKfpUiHost);
      setDeployPanelCustomLinks(deployPanelCustomLinks);
      DeployUtils.logLinksHint(resolvedKfpUiHost, deployPanelCustomLinks);

      // Only make KFP network calls when the Kale toggle is enabled.
      // This avoids hitting a potentially-absent KFP endpoint on every notebook
      // open for users who have never enabled Kale. When experiments load, they
      // enrich the already-shown metadata with the resolved experiment.
      if (backend && isEnabledRef.current) {
        const nbFilePath = getNotebookPath(notebook);
        if (nbFilePath) {
          await commands.resumeStateIfExploreNotebook(nbFilePath);
        }
        try {
          const fetchedExperiments = await fetchExperiments(notebook);
          applySavedMetadata(notebook, notebookMetadata, fetchedExperiments);
        } catch (error) {
          console.warn(
            'Kale: could not fetch experiments (KFP may be unreachable); ' +
              'notebook metadata is shown without the experiment list.',
            error,
          );
          setExperiments([]);
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
      metadataRef,
      setMetadata,
      setExperiments,
      setGettingExperiments,
      experimentsRef,
      isEnabledRef,
      applySavedMetadata,
      fetchExperiments,
    ],
  );
  // Enabling Kale on the notebook that is already open must load experiments
  // immediately. Notebook switches still go through loadNotebookPanel.
  useEffect(() => {
    if (!backend || !isEnabled) {
      return;
    }
    const notebook = tracker.currentWidget;
    if (!(notebook instanceof NotebookPanel)) {
      return;
    }
    let cancelled = false;
    fetchExperiments(notebook).catch(error => {
      if (!cancelled) {
        console.error('Failed to load KFP experiments:', error);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [backend, isEnabled, tracker, fetchExperiments]);
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
