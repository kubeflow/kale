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

import { useCallback, useRef, useState } from 'react';
import { INotebookTracker, NotebookPanel } from '@jupyterlab/notebook';
import { Kernel } from '@jupyterlab/services';
import { IDocumentManager } from '@jupyterlab/docmanager';
import { PageConfig } from '@jupyterlab/coreutils';
import { DeployProgressState } from '../deploys-progress/DeployProgress';
import {
  DefaultState,
  DeployType,
  IKaleNotebookMetadata,
} from '../LeftPanelTypes';
import Commands from '../../lib/Commands';
import NotebookUtils from '../../lib/NotebookUtils';
import { isRestrictedAccessMode } from '../../components/volumes/volumeUtils';

interface IUseDeploymentParams {
  tracker: INotebookTracker;
  kernel: Kernel.IKernelConnection;
  docManager: IDocumentManager;
  autoSaveOnCompileOrRun: boolean;
  outputPath: string;
  resolvedDefaultBaseImage: string;
}

export interface IDeploymentState {
  runDeployment: boolean;
  deployProgress: DeployProgressState | null;
  activateRunDeployState: (type: DeployType) => void;
  onPanelRemove: () => void;
  triggerCompile: () => void;
  triggerRun: () => void;
  syncRefs: (
    metadata: IKaleNotebookMetadata,
    namespace: string,
    deployDebugMessage: boolean,
  ) => void;
}

/**
 * Hook that manages the full compile/upload/run deploy lifecycle: triggering
 * deploys, tracking progress, and exposing callbacks for the toolbar and
 * deploy button.
 */
export function useDeployment({
  tracker,
  kernel,
  docManager,
  autoSaveOnCompileOrRun,
  outputPath,
  resolvedDefaultBaseImage,
}: IUseDeploymentParams): IDeploymentState {
  const [runDeployment, setRunDeployment] = useState(false);
  const [deployProgress, setDeployProgress] =
    useState<DeployProgressState | null>(null);

  const runDeploymentRef = useRef(false);
  runDeploymentRef.current = runDeployment;

  const metadataRef = useRef<IKaleNotebookMetadata>(DefaultState.metadata);
  const namespaceRef = useRef('');
  const deployDebugMessageRef = useRef(false);
  const deploymentTypeRef = useRef<DeployType>('compile');

  const syncRefs = useCallback(
    (
      metadata: IKaleNotebookMetadata,
      namespace: string,
      deployDebugMessage: boolean,
    ) => {
      metadataRef.current = metadata;
      namespaceRef.current = namespace;
      deployDebugMessageRef.current = deployDebugMessage;
    },
    [],
  );

  const updateDeployProgress = useCallback((progress: DeployProgressState) => {
    setDeployProgress(prev => (prev ? { ...prev, ...progress } : progress));
  }, []);

  const onPanelRemove = useCallback(() => {
    setDeployProgress(null);
  }, []);

  const getActiveNotebook = useCallback(
    (): NotebookPanel | null => tracker.currentWidget,
    [tracker],
  );

  const getActiveNotebookPath = useCallback(() => {
    const notebook = getActiveNotebook();
    if (!notebook) {
      return false;
    }
    return PageConfig.getOption('serverRoot') + '/' + notebook.context.path;
  }, [getActiveNotebook]);

  const runDeploymentCommand = useCallback(async () => {
    const activeNotebook = getActiveNotebook();

    if (!activeNotebook) {
      setRunDeployment(false);
      return;
    }

    if (activeNotebook.model?.dirty && !autoSaveOnCompileOrRun) {
      const result = await NotebookUtils.showYesNoDialog('Unsaved Changes', [
        'Your current Notebook contains unsaved changes. Saving is required to proceed.',
        'Would you like to save now?',
      ]);
      if (!result) {
        setRunDeployment(false);
        return;
      }
    }
    if (activeNotebook.model?.dirty) {
      await activeNotebook.context.save();
    }

    const commands = new Commands(activeNotebook, kernel);
    const progressCallback = (x: DeployProgressState) => {
      updateDeployProgress({ ...x, namespace: namespaceRef.current });
    };

    const metadata: IKaleNotebookMetadata = JSON.parse(
      JSON.stringify(metadataRef.current),
    );

    metadata.base_image = resolvedDefaultBaseImage;

    // outputPath comes from JupyterLab Settings; backend expects it as output_path.
    if (outputPath) {
      metadata.output_path = outputPath;
    }

    // Check for ReadWriteOnce volumes and warn the user
    if (metadata.volumes && metadata.volumes.length > 0) {
      try {
        const pvcs = await commands.listPvcs();
        const pvcModes = new Map(pvcs.map(p => [p.name, p.access_modes]));
        const restrictedVolumes = metadata.volumes.filter(v =>
          isRestrictedAccessMode(pvcModes.get(v.name)),
        );

        if (restrictedVolumes.length > 0) {
          const confirmed = await NotebookUtils.showYesNoDialog(
            'Volume Access Mode Warning',
            [
              'Pipeline has RWO/RWOP mounted volumes.',
              '',
              'ReadWriteOnce (RWO) volumes can only be mounted on one node. ' +
                'ReadWriteOncePod (RWOP) volumes can only be mounted by one pod. ' +
                'Parallel steps may fail if scheduled on different nodes or run concurrently.',
              '',
              'Consider using ReadWriteMany (RWX) volumes for parallel pipelines.',
              '',
              'Do you want to proceed anyway?',
            ],
            'Proceed',
            'Cancel',
          );

          if (!confirmed) {
            setRunDeployment(false);
            return;
          }
        }
      } catch {
        // If we can't check PVC modes, proceed anyway (best effort)
      }
    }

    const nbFilePath = getActiveNotebookPath();

    if (!nbFilePath) {
      progressCallback({ message: 'No active notebook path found.' });
      setRunDeployment(false);
      return;
    }

    const validationSucceeded = await commands.validateMetadata(
      nbFilePath,
      metadata,
      progressCallback,
    );
    if (!validationSucceeded) {
      setRunDeployment(false);
      return;
    }
    progressCallback({ message: 'Validation completed successfully' });

    const compileResult = await commands.compilePipeline(
      nbFilePath,
      metadata,
      docManager,
      deployDebugMessageRef.current,
      progressCallback,
    );
    if (!compileResult.success) {
      setRunDeployment(false);
      return;
    }
    progressCallback({ message: 'Notebook compiled successfully' });

    const currentDeploymentType = deploymentTypeRef.current;
    const uploadPipeline =
      currentDeploymentType === 'upload' || currentDeploymentType === 'run'
        ? await commands.uploadPipeline(
            compileResult.pipeline_package_path,
            compileResult.pipeline_metadata,
            progressCallback,
          )
        : null;

    if (!uploadPipeline) {
      setRunDeployment(false);
      progressCallback({ pipeline: false });
      return;
    }
    progressCallback({
      message: 'Pipeline uploaded successfully',
      pipeline: {
        pipeline: {
          pipelineid: uploadPipeline.pipeline.pipelineid,
          versionid: uploadPipeline.pipeline.versionid,
          name: uploadPipeline.pipeline.name,
        },
      },
    });

    if (currentDeploymentType === 'run') {
      const runPipeline = await commands.runPipeline(
        uploadPipeline.pipeline.pipelineid,
        uploadPipeline.pipeline.versionid,
        compileResult.pipeline_metadata,
        compileResult.pipeline_package_path,
        progressCallback,
      );
      if (runPipeline) {
        commands.pollRun(runPipeline, progressCallback);
      }
    }

    setRunDeployment(false);
  }, [
    getActiveNotebook,
    getActiveNotebookPath,
    kernel,
    docManager,
    autoSaveOnCompileOrRun,
    outputPath,
    resolvedDefaultBaseImage,
    updateDeployProgress,
  ]);

  const activateRunDeployState = useCallback(
    (type: DeployType) => {
      if (!runDeploymentRef.current) {
        deploymentTypeRef.current = type;
        setRunDeployment(true);
        setDeployProgress(null);
        runDeploymentCommand();
      }
    },
    [runDeploymentCommand],
  );

  const triggerCompile = useCallback(() => {
    activateRunDeployState('compile');
  }, [activateRunDeployState]);

  const triggerRun = useCallback(() => {
    activateRunDeployState('run');
  }, [activateRunDeployState]);

  return {
    runDeployment,
    deployProgress,
    activateRunDeployState,
    onPanelRemove,
    triggerCompile,
    triggerRun,
    syncRefs,
  };
}
