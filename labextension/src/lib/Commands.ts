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

import { Kernel } from '@jupyterlab/services';
import { NotebookPanel } from '@jupyterlab/notebook';
import {
  _legacy_executeRpc,
  _legacy_executeRpcAndShowRPCError,
} from './RPCUtils';

import { DeployProgressState, RunPipeline } from '../widgets/deploys-progress/DeployProgress';

type OnUpdateCallbak = (params: Partial<DeployProgressState>) => void;

import {
  IExperiment,
  IKaleNotebookMetadata,
  NEW_EXPERIMENT,
} from '../widgets/LeftPanel';
import { IDeployPanelCustomLinks } from '../widgets/LeftPanelTypes';
import NotebookUtils from './NotebookUtils';
import { IDocumentManager } from '@jupyterlab/docmanager';
import CellUtils from './CellUtils';

enum RUN_CELL_STATUS {
  OK = 'ok',
  ERROR = 'error',
}

interface ICompileNotebookArgs {
  source_notebook_path: string;
  notebook_metadata_overrides: IKaleNotebookMetadata;
  debug: boolean;
}

type ICompileNotebookResult =
  | {
      success: true;
      pipeline_package_path: string;
      pipeline_metadata: IKaleNotebookMetadata;
      script_content: string;
    }
  | { success: false };

interface IUploadPipelineArgs {
  pipeline_package_path: string;
  pipeline_metadata: object;
}

interface IUploadPipelineResp {
  already_exists: boolean;
  pipeline: { pipelineid: string; versionid: string; name: string };
}

interface IRunPipelineArgs {
  pipeline_metadata: object;
  pipeline_package_path?: string;
  pipeline_id?: string;
  version_id?: string;
}

export default class Commands {
  private readonly _notebook: NotebookPanel;
  private readonly _kernel: Kernel.IKernelConnection;

  constructor(notebook: NotebookPanel, kernel: Kernel.IKernelConnection) {
    this._notebook = notebook;
    this._kernel = kernel;
  }

  unmarshalData = async (nbFileName: string) => {
    const cmd: string =
      'from kale.rpc.nb import unmarshal_data as __kale_rpc_unmarshal_data\n' +
      `locals().update(__kale_rpc_unmarshal_data("${nbFileName}"))`;
    console.debug('Executing command: ' + cmd);
    await NotebookUtils.sendKernelRequestFromNotebook(this._notebook, cmd, {});
  };

  getDefaultBaseImage = async (): Promise<string> => {
    try {
      return await _legacy_executeRpc(
        this._notebook,
        this._kernel,
        'nb.get_default_base_image',
      );
    } catch (error) {
      console.error('Failed to retrieve default base image', error);
      return 'python:3.12';
    }
  };

  getExperiments = async (
    experiment: { id: string; name: string },
    experimentName: string,
  ) => {
    let experimentsList: IExperiment[] = await _legacy_executeRpcAndShowRPCError(
      this._notebook,
      this._kernel,
      'kfp.list_experiments',
    );
    if (experimentsList) {
      experimentsList.push(NEW_EXPERIMENT);
    } else {
      experimentsList = [NEW_EXPERIMENT];
    }

    // Fix experiment metadata
    let newExperiment: IExperiment | null = null;
    const selectedExperiments: IExperiment[] = experimentsList.filter(
      e =>
        e.id === experiment.id ||
        e.name === experiment.name ||
        e.name === experimentName,
    );
    if (
      selectedExperiments.length === 0 ||
      selectedExperiments[0].id === NEW_EXPERIMENT.id
    ) {
      let name = experimentsList[0].name;
      if (name === NEW_EXPERIMENT.name) {
        name = experiment.name !== '' ? experiment.name : experimentName;
      }
      newExperiment = { ...experimentsList[0], name: name };
    } else {
      newExperiment = selectedExperiments[0];
    }
    return {
      experiments: experimentsList,
      experiment: newExperiment,
      experiment_name: newExperiment.name,
    };
  };

  getKfpUiHost = async (): Promise<string> => {
    try {
      return await _legacy_executeRpc(
        this._notebook,
        this._kernel,
        'kfp.get_ui_host',
      );
    } catch (error) {
      console.error('Failed to retrieve KFP UI host', error);
      return '';
    }
  };

  getDeployPanelCustomLinks = async (): Promise<IDeployPanelCustomLinks> => {
    try {
      return await _legacy_executeRpc(
        this._notebook,
        this._kernel,
        'kfp.get_custom_links',
      );
    } catch (error) {
      console.error('Failed to retrieve custom links', error);
      return { upload: '', run: '' };
    }
  };

  pollRun(runPipeline: RunPipeline, onUpdate: OnUpdateCallbak) {
    _legacy_executeRpcAndShowRPCError(
      this._notebook,
      this._kernel,
      'kfp.get_run',
      {
        run_id: runPipeline.id,
      },
    ).then(run => {
      onUpdate({ runPipeline: run });
      if (run && (run.status === 'Running' || run.status === null)) {
        setTimeout(() => this.pollRun(run, onUpdate), 2000);
      }
    });
  }

  validateMetadata = async (
    notebookPath: string,
    metadata: IKaleNotebookMetadata,
    onUpdate: OnUpdateCallbak,
  ): Promise<boolean> => {
    onUpdate({ showValidationProgress: true });
    const validateNotebookArgs = {
      source_notebook_path: notebookPath,
      notebook_metadata_overrides: metadata,
    };
    const validateNotebook = await _legacy_executeRpcAndShowRPCError(
      this._notebook,
      this._kernel,
      'nb.validate_notebook',
      validateNotebookArgs,
    );
    if (validateNotebook === null) {
      onUpdate({ notebookValidation: false });
      return false;
    }
    onUpdate({ notebookValidation: validateNotebook });
    return validateNotebook;
  };

  // todo: docManager needs to be passed to deploysProgress during init
  // todo: autosnapshot will become part of metadata
  // todo: deployDebugMessage will be removed (the "Debug" toggle is of no use
  //  anymore
  compilePipeline = async (
    notebookPath: string,
    metadata: IKaleNotebookMetadata,
    docManager: IDocumentManager,
    deployDebugMessage: boolean,
    onUpdate: OnUpdateCallbak,
  ): Promise<ICompileNotebookResult> => {
    onUpdate({ showCompileProgress: true, docManager: docManager });
    const compileNotebookArgs: ICompileNotebookArgs = {
      source_notebook_path: notebookPath,
      notebook_metadata_overrides: metadata,
      debug: deployDebugMessage,
    };
    const compileNotebook = await _legacy_executeRpcAndShowRPCError(
      this._notebook,
      this._kernel,
      'nb.compile_notebook',
      compileNotebookArgs,
    );
    if (!compileNotebook) {
      onUpdate({ compiledPath: 'error' });
      return { success: false };
    }
    // Pass to the deploy progress the path to the generated py script:
    // compileNotebook is the name of the tar package, that generated in the
    // workdir. Instead, the python script has a slightly different name and
    // is generated in the same directory where the notebook lives.
    onUpdate({
      compiledPath: compileNotebook.pipeline_package_path.replace(
        'pipeline.yaml',
        'kale.py',
      ),
      compiledContent: compileNotebook.script_content,
    });
    return {
      success: true,
      pipeline_package_path: compileNotebook.pipeline_package_path,
      pipeline_metadata: compileNotebook.pipeline_metadata,
      script_content: compileNotebook.script_content,
    };
  };

  uploadPipeline = async (
    compiledPackagePath: string,
    compiledPipelineMetadata: IKaleNotebookMetadata,
    onUpdate: OnUpdateCallbak,
  ): Promise<IUploadPipelineResp> => {
    onUpdate({ showUploadProgress: true });
    const uploadPipelineArgs: IUploadPipelineArgs = {
      pipeline_package_path: compiledPackagePath,
      pipeline_metadata: compiledPipelineMetadata,
    };
    const uploadPipeline: IUploadPipelineResp = await _legacy_executeRpcAndShowRPCError(
      this._notebook,
      this._kernel,
      'kfp.upload_pipeline',
      uploadPipelineArgs,
    );
    const result = true;
    if (!uploadPipeline) {
      onUpdate({ showUploadProgress: false, pipeline: false });
      return uploadPipeline;
    }
    if (uploadPipeline && result) {
      onUpdate({ pipeline: uploadPipeline });
    }
    return uploadPipeline;
  };

  runPipeline = async (
    pipelineId: string,
    versionId: string,
    compiledPipelineMetadata: IKaleNotebookMetadata,
    pipelinePackagePath: string,
    onUpdate: (params: { showRunProgress?: boolean, runPipeline?: boolean }) => void,
  ) => {
    onUpdate({ showRunProgress: true });
    const runPipelineArgs: IRunPipelineArgs = {
      pipeline_metadata: compiledPipelineMetadata,
      pipeline_id: pipelineId,
      version_id: versionId,
      pipeline_package_path: pipelinePackagePath,
    };
    const runPipeline = await _legacy_executeRpcAndShowRPCError(
      this._notebook,
      this._kernel,
      'kfp.run_pipeline',
      runPipelineArgs,
    );
    if (runPipeline) {
      onUpdate({ runPipeline });
    } else {
      onUpdate({ showRunProgress: false, runPipeline: false });
    }
    return runPipeline;
  };

  resumeStateIfExploreNotebook = async (notebookPath: string) => {
    const exploration = await _legacy_executeRpcAndShowRPCError(
      this._notebook,
      this._kernel,
      'nb.explore_notebook',
      { source_notebook_path: notebookPath },
    );

    if (!exploration || !exploration.is_exploration) {
      return;
    }

    NotebookUtils.clearCellOutputs(this._notebook);
    const title = 'Notebook Exploration';
    let message: string[] = [];
    const runCellResponse = await NotebookUtils.runGlobalCells(this._notebook);
    if (runCellResponse.status === RUN_CELL_STATUS.OK) {
      // unmarshalData runs in the same kernel as the .ipynb, so it requires the
      // filename
      await this.unmarshalData(notebookPath.split('/').pop() || '');
      const cell = CellUtils.getCellByStepName(
        this._notebook,
        exploration.step_name,
      );
      message = [`Resuming notebook at step: "${exploration.step_name}"`];
      if (cell) {
        NotebookUtils.selectAndScrollToCell(this._notebook, cell);
      } else {
        message.push('ERROR: Could not retrieve step\'s position.');
      }
    } else {
      message = [
        `Executing "${runCellResponse.cellType}" cell failed.\n` +
        `Resuming notebook at cell index ${runCellResponse.cellIndex}.`,
        `Error name: ${runCellResponse.ename}`,
        `Error value: ${runCellResponse.evalue}`,
      ];
    }
    await NotebookUtils.showMessage(title, message);
    await _legacy_executeRpcAndShowRPCError(
      this._notebook,
      this._kernel,
      'nb.remove_marshal_dir',
      {
        source_notebook_path: notebookPath,
      },
    );
  };

  findPodDefaultLabelsOnServer = async (): Promise<{
    [key: string]: string;
  }> => {
    const labels: {
      [key: string]: string;
    } = {};
    try {
      return await _legacy_executeRpc(
        this._notebook,
        this._kernel,
        'nb.find_poddefault_labels_on_server',
      );
    } catch (error) {
      console.error('Failed to retrieve PodDefaults applied on server', error);
      return labels;
    }
  };

  getNamespace = async (): Promise<string> => {
    try {
      return await _legacy_executeRpc(
        this._notebook,
        this._kernel,
        'nb.get_namespace',
      );
    } catch (error) {
      console.warn(
        "Could not detect the notebook's namespace. " +
        'Pipeline and run links may not include the correct namespace parameter.'
      );
      return '';
    }
  };

  listPvcs = async (): Promise<Array<{ name: string; access_modes: string[] }>> => {
    try {
      const result = await _legacy_executeRpc(
        this._notebook,
        this._kernel,
        'nb.list_pvcs',
      );
      return result || [];
    } catch (error) {
      console.warn('Could not list PVCs — combobox will show no suggestions.', error);
      return [];
    }
  };

  listNotebookVolumes = async (): Promise<
    Array<{ name: string; mount_point: string; access_modes?: string[] }>
  > => {
    try {
      const result = await _legacy_executeRpc(
        this._notebook,
        this._kernel,
        'nb.list_notebook_volumes',
      );
      return result || [];
    } catch {
      // nb.list_notebook_volumes may not be implemented yet; degrade gracefully.
      return [];
    }
  };
}
