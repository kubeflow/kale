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

/**
 * Kale left-panel entry point for per-cell pipeline metadata in the notebook.
 *
 * Renders the global Enable switch. When turned on, it overlays each code cell
 * with InlineMetadata (step name, dependencies, limits) and mounts a single
 * CellMetadataEditor portal for the active cell. Notebook signals (cell changes,
 * saves, selection) are handled in hooks; editor visibility is shared via
 * CellMetadataContext.
 */

import * as React from 'react';
import { useState, useEffect, useCallback, useRef } from 'react';
import { NotebookPanel } from '@jupyterlab/notebook';
import { CellMetadataEditor, ICellEditorData } from './CellMetadataEditor';
import { CellMetadataContext } from '../../lib/CellMetadataContext';
import { Switch } from '@mui/material';
import NotebookUtils from '../../lib/NotebookUtils';
import { createPortal } from 'react-dom';
import { useActiveCellIndex } from './hooks/useActiveCellIndex';
import { useInlineMetadata } from './hooks/useInlineMetadata';

interface IProps {
  notebook: NotebookPanel;
  onMetadataEnable: (isEnabled: boolean) => void;
  resolvedDefaultBaseImage: string;
  runtimeImages: Record<string, string>;
  composableNotebooks: boolean;
  initialChecked?: boolean;
}

export const InlineCellsMetadata: React.FC<IProps> = ({
  notebook,
  onMetadataEnable,
  resolvedDefaultBaseImage,
  runtimeImages,
  composableNotebooks,
  initialChecked,
}) => {
  const [checked, setChecked] = useState(false);
  const [isEditorVisible, setIsEditorVisible] = useState(false);

  const activeCellIndex = useActiveCellIndex(notebook);

  const { editors, metadataCmp } = useInlineMetadata(
    notebook,
    checked,
    activeCellIndex,
    {
      resolvedDefaultBaseImage,
      runtimeImages,
      onActiveMetadataChange: () => setIsEditorVisible(true),
      onCellsChanged: () => setIsEditorVisible(false),
    },
  );

  useEffect(() => {
    setIsEditorVisible(false);
  }, [notebook]);

  useEffect(() => {
    if (initialChecked !== undefined && initialChecked !== checked) {
      setChecked(initialChecked);
    }
  }, [initialChecked]);

  const runEnableKaleLogic = useCallback(() => {
    if (!notebook?.model) {
      return;
    }
    notebook.context.ready.then(() => {
      if (
        notebook?.content?.activeCellIndex !== undefined &&
        notebook.content.activeCellIndex >= 0
      ) {
        const activeCell = notebook.content.activeCell;
        if (activeCell?.node) {
          setTimeout(NotebookUtils.selectAndScrollToCell, 200, notebook, {
            cell: activeCell,
            index: notebook.content.activeCellIndex,
          });
        }
      }
    });
  }, [notebook]);

  const prevCheckedRef = useRef(checked);
  useEffect(() => {
    if (!prevCheckedRef.current && checked && notebook) {
      runEnableKaleLogic();
    }
    prevCheckedRef.current = checked;
  }, [checked, notebook, runEnableKaleLogic]);

  const toggleGlobalKaleSwitch = useCallback(
    (newChecked: boolean) => {
      setChecked(newChecked);
      onMetadataEnable(newChecked);

      if (!newChecked) {
        setIsEditorVisible(false);
      }
    },
    [onMetadataEnable],
  );

  const onEditorVisibilityChange = useCallback((visible: boolean) => {
    setIsEditorVisible(visible);
  }, []);

  const activeEditorData = editors[activeCellIndex];
  const editorProps: ICellEditorData = activeEditorData
    ? {
        notebook: activeEditorData.notebook,
        stepName: activeEditorData.stepName || '',
        stepDependencies: activeEditorData.stepDependencies || [],
        limits: activeEditorData.limits || {},
        secrets: activeEditorData.secrets || {},
        baseImage: activeEditorData.baseImage,
        enableCaching: activeEditorData.enableCaching,
        notebookPath: activeEditorData.notebookPath,
        generateHtmlReport: activeEditorData.generateHtmlReport,
      }
    : {
        notebook: notebook,
        stepName: '',
        stepDependencies: [],
        limits: {},
        secrets: {},
        baseImage: undefined,
        enableCaching: undefined,
        notebookPath: undefined,
        generateHtmlReport: undefined,
      };

  const cellMetadataEditor = createPortal(
    <CellMetadataEditor
      notebook={editorProps.notebook}
      stepName={editorProps.stepName}
      stepDependencies={editorProps.stepDependencies}
      limits={editorProps.limits}
      secrets={editorProps.secrets}
      baseImage={editorProps.baseImage}
      enableCaching={editorProps.enableCaching}
      notebookPath={editorProps.notebookPath}
      generateHtmlReport={editorProps.generateHtmlReport}
      resolvedDefaultBaseImage={resolvedDefaultBaseImage}
      runtimeImages={runtimeImages}
    />,
    document.body,
  );

  return (
    <React.Fragment>
      <div className="toolbar input-container">
        <div className={'switch-label'}>Enable</div>
        <Switch
          checked={checked}
          onChange={c => toggleGlobalKaleSwitch(c.target.checked)}
          color="primary"
          name="enableKale"
          inputProps={{ 'aria-label': 'primary checkbox' }}
          classes={{ root: 'material-switch' }}
        />
      </div>
      <div>
        <CellMetadataContext.Provider
          value={{
            activeCellIndex,
            isEditorVisible,
            onEditorVisibilityChange,
            composableNotebooks,
          }}
        >
          {cellMetadataEditor}
          {metadataCmp}
        </CellMetadataContext.Provider>
      </div>
    </React.Fragment>
  );
};
