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
import { useCallback, useContext, useRef, useState } from 'react';
import { NotebookPanel } from '@jupyterlab/notebook';
import TagsUtils, { ISecretRef } from '../../lib/TagsUtils';
import CloseIcon from '@mui/icons-material/Close';
import LayersClearIcon from '@mui/icons-material/LayersClear';
import SettingsIcon from '@mui/icons-material/Settings';
import ColorUtils from '../../lib/ColorUtils';
import { CellMetadataContext } from '../../lib/CellMetadataContext';
import { IconButton, Tooltip } from '@mui/material';
import { Input } from '../../components/Input';
import { Select } from '../../components/Select';
import { SelectMulti } from '../../components/SelectMulti';
import { StepConfigDialog } from './dialogs/StepConfigDialog';
import { useUpdateCellTags } from './hooks/useCellTags';
import { useEditorPosition } from './hooks/useEditorPosition';
import {
  CELL_TYPES,
  NOTEBOOK_PATH_ERROR_MSG,
  RESERVED_CELL_NAMES,
  STEP_NAME_ERROR_MSG,
} from './constants';

export {
  RESERVED_CELL_NAMES,
  RESERVED_CELL_NAMES_HELP_TEXT,
  RESERVED_CELL_NAMES_CHIP_COLOR,
} from './constants';

export interface ICellEditorData {
  notebook: NotebookPanel;
  stepName?: string;
  stepDependencies: string[];
  limits?: { [id: string]: string };
  secrets?: { [envName: string]: ISecretRef };
  baseImage?: string;
  enableCaching?: boolean;
  notebookPath?: string;
  generateHtmlReport?: boolean;
}

export interface IProps extends ICellEditorData {
  resolvedDefaultBaseImage: string;
  runtimeImages: Record<string, string>;
}

export const CellMetadataEditor: React.FC<IProps> = props => {
  const {
    notebook,
    stepName = '',
    stepDependencies,
    limits = {},
    secrets = {},
    baseImage,
    enableCaching,
    notebookPath,
    generateHtmlReport,
    resolvedDefaultBaseImage,
    runtimeImages,
  } = props;

  const {
    activeCellIndex,
    isEditorVisible,
    onEditorVisibilityChange,
    composableNotebooks,
  } = useContext(CellMetadataContext);

  // multi-notebook composition is still in development, so the cell type is
  // offered only where it has been switched on
  const cellTypes = composableNotebooks
    ? CELL_TYPES
    : CELL_TYPES.filter(t => t.value !== 'notebook');

  const editorRef = useRef<HTMLDivElement>(null);

  const updateCellTags = useUpdateCellTags({
    notebook,
    stepName,
    stepDependencies,
    limits,
    secrets,
    baseImage,
    enableCaching,
    notebookPath,
    generateHtmlReport,
  });

  useEditorPosition(editorRef, notebook);

  const stepDependenciesChoices = React.useMemo(() => {
    if (!notebook) {
      return [];
    }
    const allSteps = TagsUtils.getAllSteps(notebook.content, activeCellIndex);
    return allSteps
      .filter(el => !RESERVED_CELL_NAMES.includes(el) && el !== stepName)
      .map(name => ({ value: name, color: `#${ColorUtils.getColor(name)}` }));
  }, [notebook, stepName, stepDependencies, activeCellIndex]);

  const previousStepName = React.useMemo(
    () =>
      notebook
        ? TagsUtils.getPreviousStep(notebook.content, activeCellIndex)
        : undefined,
    [notebook, activeCellIndex, stepName],
  );

  const isNotebookRef = stepName.startsWith('notebook:');
  const cellType = isNotebookRef
    ? 'notebook'
    : RESERVED_CELL_NAMES.includes(stepName)
      ? stepName
      : 'step';
  const cellColor = stepName
    ? `#${ColorUtils.getColor(stepName)}`
    : 'transparent';
  const isStep = cellType === 'step';
  const hasStepName = !!(stepName && stepName.length > 0);

  const prevStepNotice =
    previousStepName && stepName === ''
      ? `Leave the step name empty to merge the cell to step '${previousStepName}'`
      : null;

  const [stepNameErrorMsg, setStepNameErrorMsg] = useState(STEP_NAME_ERROR_MSG);

  const onBeforeUpdate = useCallback(
    (value: string) => {
      if (value === stepName) {
        return false;
      }
      const stepNames = TagsUtils.getAllSteps(notebook.content);
      if (stepNames.includes(value)) {
        setStepNameErrorMsg('This name already exists.');
        return true;
      }
      setStepNameErrorMsg(STEP_NAME_ERROR_MSG);
      return false;
    },
    [notebook, stepName],
  );

  const [configDialogOpen, setConfigDialogOpen] = useState(false);

  const closeEditor = useCallback(() => {
    onEditorVisibilityChange(false);
  }, [onEditorVisibilityChange]);

  return (
    <>
      <div>
        <div
          className={
            'kale-metadata-editor-wrapper' +
            (isEditorVisible ? ' opened' : '') +
            (isStep ? ' kale-is-step' : '')
          }
          ref={editorRef}
        >
          <div
            className={
              'kale-cell-metadata-editor' + (isEditorVisible ? '' : ' hidden')
            }
            style={{ borderLeft: `2px solid ${cellColor}` }}
          >
            <Select
              updateValue={updateCellTags.updateCellType}
              values={cellTypes}
              value={cellType || 'step'}
              label={'Cell type'}
              index={0}
              variant="outlined"
              style={{ width: '30%' }}
            />

            {isNotebookRef && (
              <Input
                label={'Notebook path'}
                updateValue={updateCellTags.updateNotebookPath}
                value={notebookPath || ''}
                regex={'^.*\\.ipynb$'}
                regexErrorMsg={NOTEBOOK_PATH_ERROR_MSG}
                variant="outlined"
                style={{ width: '60%' }}
              />
            )}

            {isStep && (
              <>
                <Input
                  label={'Step name'}
                  updateValue={updateCellTags.updateStepName}
                  value={stepName}
                  regex={'^([_a-z]([_a-z0-9]*)?)?$'}
                  regexErrorMsg={stepNameErrorMsg}
                  variant="outlined"
                  onBeforeUpdate={onBeforeUpdate}
                  style={{ width: '30%' }}
                />

                <Tooltip
                  title={
                    !hasStepName
                      ? 'Please enter a step name first'
                      : stepDependenciesChoices.length === 0
                        ? 'No other steps available. Add more pipeline steps to create dependencies.'
                        : 'Select which steps this step depends on'
                  }
                  placement="top"
                  arrow
                >
                  <div style={{ width: '30%', marginRight: '4px' }}>
                    <SelectMulti
                      id="select-previous-steps"
                      label="Depends on"
                      disabled={
                        !hasStepName || stepDependenciesChoices.length === 0
                      }
                      updateSelected={updateCellTags.updateDependencies}
                      options={stepDependenciesChoices}
                      variant="outlined"
                      selected={stepDependencies || []}
                    />
                  </div>
                </Tooltip>

                <Tooltip title="Configure step" placement="top" arrow>
                  <span>
                    <IconButton
                      aria-label="Configure step"
                      disabled={!hasStepName}
                      onClick={() => setConfigDialogOpen(true)}
                      size="small"
                    >
                      <SettingsIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
              </>
            )}

            {(hasStepName || RESERVED_CELL_NAMES.includes(stepName)) && (
              <Tooltip title="Clear all cell metadata" placement="top" arrow>
                <IconButton
                  aria-label="clear metadata"
                  onMouseDown={updateCellTags.clearCellMetadata}
                  size="small"
                >
                  <LayersClearIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}

            <IconButton aria-label="close editor" onMouseDown={closeEditor}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </div>
          <div
            className={
              'kale-cell-metadata-editor-helper-text' +
              (isEditorVisible ? '' : ' hidden')
            }
          >
            <p>{prevStepNotice}</p>
          </div>
        </div>
      </div>

      <StepConfigDialog
        open={configDialogOpen}
        onClose={() => setConfigDialogOpen(false)}
        stepName={stepName}
        limits={limits}
        updateLimits={updateCellTags.updateLimits}
        secrets={secrets}
        updateSecrets={updateCellTags.updateSecrets}
        baseImage={baseImage}
        resolvedDefaultBaseImage={resolvedDefaultBaseImage}
        runtimeImages={runtimeImages}
        onUpdateBaseImage={updateCellTags.updateBaseImage}
        enableCaching={enableCaching}
        onUpdateCaching={updateCellTags.updateCaching}
        generateHtmlReport={generateHtmlReport}
        onUpdateHtmlReport={updateCellTags.updateHtmlReport}
      />
    </>
  );
};
