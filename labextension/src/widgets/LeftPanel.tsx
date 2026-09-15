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

import * as React from 'react';
import { useEffect } from 'react';
import { INotebookTracker } from '@jupyterlab/notebook';
import { InlineCellsMetadata } from './cell-metadata/InlineCellsMetadata';
import { SplitDeployButton } from '../components/DeployButton';
import { Kernel } from '@jupyterlab/services';
import { ExperimentInput } from '../components/ExperimentInput';
import { DeployProgress } from './deploys-progress/DeployProgress';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { IDocumentManager } from '@jupyterlab/docmanager';
import { ThemeProvider } from '@mui/material/styles';
import { FormControlLabel, Link, Switch } from '@mui/material';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import { theme } from '../Theme';
import { Input } from '../components/Input';
import { VolumesPanel } from '../components/VolumesPanel';
import { KaleEmptyState } from './KaleEmptyState';
import { KFPStatusBadge } from '../components/KFPStatusBadge';
import kaleLogo from '../../style/icons/kale.svg';
import { useKfpStatus } from './hooks/useKfpStatus';
import { useActiveNotebook } from './hooks/useActiveNotebook';
import { useNotebookMetadata } from './hooks/useNotebookMetadata';
import { useDeployment } from './hooks/useDeployment';
import { setLeftPanelCallbacks } from '../commands/kaleToolbar';
import { resolveDefaultBaseImage } from '../lib/resolveDefaultBaseImage';

import {
  DeployType,
  IExperiment,
  IKaleNotebookMetadata,
  ISecurityContext,
  DefaultState,
  NEW_EXPERIMENT,
  PIPELINE_NAME_MAX_LENGTH,
  IVolumeConfig,
} from './LeftPanelTypes';
export type { DeployType, IExperiment, IKaleNotebookMetadata, IVolumeConfig };
export { DefaultState, NEW_EXPERIMENT };

interface IProps {
  lab: JupyterFrontEnd;
  tracker: INotebookTracker;
  docManager: IDocumentManager;
  backend: boolean;
  kernel: Kernel.IKernelConnection;
  enableKaleByDefault: boolean;
  autoSaveOnCompileOrRun: boolean;
  enableComposableNotebooks: boolean;
  defaultBaseImageSetting: string;
  runtimeImages: string[];
  envDefaultBaseImage: string;
  securityContext: ISecurityContext;
  outputPath: string;
}

export const KubeflowKaleLeftPanel: React.FC<IProps> = props => {
  const {
    lab,
    tracker,
    backend,
    kernel,
    docManager,
    enableKaleByDefault,
    autoSaveOnCompileOrRun,
    enableComposableNotebooks,
    defaultBaseImageSetting,
    runtimeImages,
    envDefaultBaseImage,
    securityContext,
    outputPath,
  } = props;

  const resolvedDefaultBaseImage = resolveDefaultBaseImage(
    defaultBaseImageSetting,
    envDefaultBaseImage,
  );

  const kfpStatus = useKfpStatus(kernel, backend);

  const activeNotebook = useActiveNotebook(tracker);

  const notebookMeta = useNotebookMetadata({
    tracker,
    backend,
    kernel,
    enableKaleByDefault,
  });

  const deployment = useDeployment({
    tracker,
    kernel,
    docManager,
    autoSaveOnCompileOrRun,
    outputPath,
    resolvedDefaultBaseImage,
  });

  const openKaleSettings = () => {
    // Settings Editor filter matches schema title, not plugin id.
    lab.commands.execute('settingeditor:open', { query: 'Kale' });
  };

  // Keep deployment refs in sync with current metadata/namespace
  // Use JupyterLab settings security_context as default if notebook doesn't have one
  const metadataWithSecurityContext = {
    ...notebookMeta.metadata,
    security_context: notebookMeta.metadata.security_context ?? securityContext,
  };
  deployment.syncRefs(
    metadataWithSecurityContext,
    notebookMeta.namespace,
    false,
  );

  // Register toolbar callbacks on mount, clear on unmount
  useEffect(() => {
    setLeftPanelCallbacks({
      triggerCompile: deployment.triggerCompile,
      triggerRun: deployment.triggerRun,
      isKaleEnabled: () => notebookMeta.isEnabled,
    });
    return () => setLeftPanelCallbacks(null);
  }, [
    deployment.triggerCompile,
    deployment.triggerRun,
    notebookMeta.isEnabled,
  ]);

  // --- render logic ---

  const selectedExperiments: IExperiment[] = notebookMeta.experiments.filter(
    e =>
      e.id === notebookMeta.metadata.experiment.id ||
      e.name === notebookMeta.metadata.experiment.name,
  );
  if (notebookMeta.experiments.length > 0 && selectedExperiments.length === 0) {
    selectedExperiments.push(notebookMeta.experiments[0]);
  }
  let experimentInputSelected = '';
  let experimentInputValue = '';
  if (selectedExperiments.length > 0) {
    experimentInputSelected = selectedExperiments[0].id;
    if (selectedExperiments[0].id === NEW_EXPERIMENT.id) {
      if (notebookMeta.metadata.experiment.name !== '') {
        experimentInputValue = notebookMeta.metadata.experiment.name;
      } else {
        experimentInputValue = notebookMeta.metadata.experiment_name;
      }
    } else {
      experimentInputValue = selectedExperiments[0].name;
    }
  }
  const pipelineNameValid =
    /^[a-z0-9]([-a-z0-9]*[a-z0-9])?$/.test(
      notebookMeta.metadata.pipeline_name,
    ) && notebookMeta.metadata.pipeline_name.length <= PIPELINE_NAME_MAX_LENGTH;
  const experimentNameRegex = /^[a-z]([-a-z0-9]*[a-z0-9])?$/;
  const experimentNameValid =
    experimentInputSelected !== NEW_EXPERIMENT.id ||
    experimentNameRegex.test(experimentInputValue);

  const experiment_name_input = (
    <ExperimentInput
      updateValue={notebookMeta.updateExperiment}
      options={notebookMeta.experiments}
      selected={experimentInputSelected}
      value={experimentInputValue}
      loading={notebookMeta.gettingExperiments}
    />
  );

  const pipeline_name_input = (
    <Input
      variant="standard"
      inputIndex={0}
      label={'Pipeline Name'}
      updateValue={notebookMeta.updatePipelineName}
      value={notebookMeta.metadata.pipeline_name}
      regex={'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'}
      regexErrorMsg={
        "Pipeline name must consist of lower case alphanumeric characters or '-', and must start and end with an alphanumeric character."
      }
      maxLength={PIPELINE_NAME_MAX_LENGTH}
      maxLengthErrorMsg={`Pipeline name must be ${PIPELINE_NAME_MAX_LENGTH} characters or fewer.`}
    />
  );

  const pipeline_desc_input = (
    <Input
      variant="standard"
      inputIndex={0}
      label={'Pipeline Description'}
      updateValue={notebookMeta.updatePipelineDescription}
      value={notebookMeta.metadata.pipeline_description}
    />
  );

  const enable_caching_toggle = (
    <FormControlLabel
      control={
        <Switch
          checked={notebookMeta.metadata.enable_caching ?? true}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            notebookMeta.updateEnableCaching(e.target.checked)
          }
          color="primary"
        />
      }
      label="Enable Pipeline Caching"
    />
  );

  return (
    <ThemeProvider theme={theme}>
      <div className={'kubeflow-widget'} key="kale-widget">
        <div className={'kubeflow-widget-content'}>
          <div>
            <p
              className="kale-header kale-main-header"
              style={{ color: theme.kale.headers.main }}
            >
              Kale
              <img
                src={`data:image/svg+xml,${encodeURIComponent(kaleLogo)}`}
                className="kale-logo-img"
                alt="Kale Logo"
              />
            </p>
            {backend && (
              <div className="kfp-status-container">
                <KFPStatusBadge status={kfpStatus} />
              </div>
            )}
          </div>

          <div className="kale-component">
            {activeNotebook ? (
              <InlineCellsMetadata
                onMetadataEnable={notebookMeta.setIsEnabled}
                notebook={activeNotebook}
                resolvedDefaultBaseImage={resolvedDefaultBaseImage}
                runtimeImages={runtimeImages}
                composableNotebooks={enableComposableNotebooks}
                initialChecked={notebookMeta.isEnabled}
              />
            ) : (
              <>
                <div className="toolbar input-container kale-disabled-toggle">
                  <div className={'switch-label'}>Enable</div>
                  <Switch
                    disabled
                    checked={false}
                    color="primary"
                    name="enableKale"
                    slotProps={{ input: { 'aria-label': 'Enable Kale' } }}
                    classes={{ root: 'material-switch' }}
                  />
                </div>
                <div className="kale-no-notebook-message">
                  <p className="kale-no-notebook-text">
                    Open a notebook to start working with Kale
                  </p>
                </div>
              </>
            )}
            {!notebookMeta.isEnabled && <KaleEmptyState />}
          </div>

          <div
            className={
              'kale-component ' +
              (notebookMeta.isEnabled && activeNotebook ? '' : 'hidden')
            }
          >
            <div>
              <p
                className="kale-header"
                style={{ color: theme.kale.headers.main }}
              >
                Pipeline Metadata
              </p>
            </div>

            <div className={'input-container'}>
              {experiment_name_input}
              {pipeline_name_input}
              {pipeline_desc_input}
              {enable_caching_toggle}
            </div>
          </div>

          <div
            className={
              'kale-component ' +
              (notebookMeta.isEnabled && activeNotebook ? '' : 'hidden')
            }
          >
            <div>
              <p
                className="kale-header"
                style={{ color: theme.kale.headers.main }}
              >
                Volumes
              </p>
            </div>
            <div className={'input-container'}>
              <VolumesPanel
                volumes={notebookMeta.metadata.volumes ?? []}
                updateVolumes={notebookMeta.updateVolumes}
                notebook={activeNotebook}
                kernel={kernel}
              />
            </div>
          </div>

          <div
            className={notebookMeta.isEnabled && activeNotebook ? '' : 'hidden'}
          >
            <div className="kale-settings-notice">
              <SettingsOutlinedIcon
                className="kale-settings-notice-icon"
                fontSize="small"
              />
              <span>
                Advanced Kale settings live in JupyterLab Settings.{' '}
                <Link
                  component="button"
                  type="button"
                  underline="hover"
                  onClick={openKaleSettings}
                  sx={{ color: theme.kale.headers.main }}
                >
                  Open settings
                </Link>
              </span>
            </div>
          </div>
        </div>
        <div
          className={notebookMeta.isEnabled && activeNotebook ? '' : 'hidden'}
          style={{ marginTop: 'auto' }}
        >
          {deployment.deployProgress && (
            <DeployProgress
              {...deployment.deployProgress}
              onRemove={deployment.onPanelRemove}
              kfpUiHost={notebookMeta.kfpUiHost}
              deployPanelCustomLinks={notebookMeta.deployPanelCustomLinks}
            />
          )}
          <SplitDeployButton
            running={deployment.runDeployment}
            handleClick={deployment.activateRunDeployState}
            disabled={!pipelineNameValid || !experimentNameValid}
          />
        </div>
      </div>
    </ThemeProvider>
  );
};
