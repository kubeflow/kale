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

import { useCallback, useContext } from 'react';
import { NotebookPanel } from '@jupyterlab/notebook';
import TagsUtils, { ISecretRef } from '../../../lib/TagsUtils';
import { CellMetadataContext } from '../../../lib/CellMetadataContext';
import { RESERVED_CELL_NAMES, NOTEBOOK_REF_CELL_HINT } from '../constants';
import CellUtils from '../../../lib/CellUtils';

interface IUseCellTagsParams {
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

/**
 * Derive the reference name for a `notebook:<name>` tag from the referenced
 * notebook's file name, sanitized the same way the backend derives module
 * names (lowercase, separators to '_', must not start with a digit).
 */
export function notebookRefNameFromPath(path: string): string {
  const base = path.split('/').pop() || '';
  let name = base
    .replace(/\.ipynb$/, '')
    .toLowerCase()
    .replace(/[-\s]+/g, '_')
    .replace(/[^a-z0-9_]/g, '');
  if (name && !/^[_a-z]/.test(name)) {
    name = 'nb_' + name;
  }
  return name;
}

/**
 * Hook that encapsulates all Kale cell metadata write operations.
 * Each returned function reads the current tags, merges the change,
 * and writes back via TagsUtils.
 */
export function useUpdateCellTags({
  notebook,
  stepName,
  stepDependencies,
  limits,
  secrets,
  baseImage,
  enableCaching,
  notebookPath,
  generateHtmlReport,
}: IUseCellTagsParams) {
  const { activeCellIndex } = useContext(CellMetadataContext);

  const updateStepName = useCallback(
    (value: string) => {
      const oldStepName = stepName || '';
      TagsUtils.updateKaleCellsTags(notebook, oldStepName, value);
      TagsUtils.setKaleCellTags(notebook, activeCellIndex, {
        prevStepNames: stepDependencies,
        limits: limits || {},
        secrets: secrets || {},
        baseImage,
        enableCaching,
        notebookPath,
        generateHtmlReport,
        stepName: value,
      });
    },
    [
      notebook,
      activeCellIndex,
      stepName,
      stepDependencies,
      limits,
      secrets,
      baseImage,
      enableCaching,
      notebookPath,
      generateHtmlReport,
    ],
  );

  const updateCellType = useCallback(
    (value: string) => {
      if (RESERVED_CELL_NAMES.includes(value)) {
        updateStepName(value);
      } else if (value === 'notebook') {
        // an empty reference; the name is derived once the path is entered
        updateStepName('notebook:');
        // a reference cell holds no code of its own, so say so in the cell
        // itself. Only when it is empty: existing code is the user's, and the
        // compiler reports it rather than this quietly overwriting it.
        const cell = CellUtils.getCell(notebook.content, activeCellIndex);
        if (!(cell?.sharedModel?.getSource() ?? '').trim()) {
          CellUtils.injectCodeAtIndex(
            notebook.content,
            activeCellIndex,
            NOTEBOOK_REF_CELL_HINT,
          );
        }
      } else {
        TagsUtils.resetCell(notebook, activeCellIndex, stepName || '');
      }
    },
    [notebook, activeCellIndex, stepName, updateStepName],
  );

  const updateNotebookPath = useCallback(
    (value: string) => {
      TagsUtils.setKaleCellTags(notebook, activeCellIndex, {
        stepName: 'notebook:' + notebookRefNameFromPath(value),
        prevStepNames: [],
        limits: {},
        baseImage: undefined,
        enableCaching: undefined,
        notebookPath: value,
      });
    },
    [notebook, activeCellIndex],
  );

  const updateDependencies = useCallback(
    (previousSteps: string[]) => {
      TagsUtils.setKaleCellTags(notebook, activeCellIndex, {
        stepName: stepName || '',
        limits: limits || {},
        secrets: secrets || {},
        baseImage,
        enableCaching,
        generateHtmlReport,
        prevStepNames: previousSteps,
      });
    },
    [
      notebook,
      activeCellIndex,
      stepName,
      limits,
      secrets,
      baseImage,
      enableCaching,
      generateHtmlReport,
    ],
  );

  const updateLimits = useCallback(
    (
      actions: {
        action: 'update' | 'delete';
        limitKey: string;
        limitValue?: string;
      }[],
    ) => {
      const newLimits = { ...limits };
      actions.forEach(a => {
        if (a.action === 'update' && a.limitValue !== undefined) {
          newLimits[a.limitKey] = a.limitValue;
        }
        if (
          a.action === 'delete' &&
          Object.keys(limits || {}).includes(a.limitKey)
        ) {
          delete newLimits[a.limitKey];
        }
      });

      TagsUtils.setKaleCellTags(notebook, activeCellIndex, {
        stepName: stepName || '',
        prevStepNames: stepDependencies,
        limits: newLimits,
        secrets: secrets || {},
        baseImage,
        enableCaching,
        generateHtmlReport,
      });
    },
    [
      notebook,
      activeCellIndex,
      stepName,
      stepDependencies,
      limits,
      secrets,
      baseImage,
      enableCaching,
      generateHtmlReport,
    ],
  );

  const updateSecrets = useCallback(
    (newSecrets: { [envName: string]: ISecretRef }) => {
      TagsUtils.setKaleCellTags(notebook, activeCellIndex, {
        stepName: stepName || '',
        prevStepNames: stepDependencies,
        limits: limits || {},
        secrets: newSecrets,
        baseImage,
        enableCaching,
        generateHtmlReport,
      });
    },
    [
      notebook,
      activeCellIndex,
      stepName,
      stepDependencies,
      limits,
      baseImage,
      enableCaching,
      generateHtmlReport,
    ],
  );

  const updateBaseImage = useCallback(
    (value: string) => {
      TagsUtils.setKaleCellTags(notebook, activeCellIndex, {
        stepName: stepName || '',
        prevStepNames: stepDependencies,
        limits: limits || {},
        secrets: secrets || {},
        baseImage: value || undefined,
        enableCaching,
        generateHtmlReport,
      });
    },
    [
      notebook,
      activeCellIndex,
      stepName,
      stepDependencies,
      limits,
      secrets,
      enableCaching,
      generateHtmlReport,
    ],
  );

  const updateCaching = useCallback(
    (value: boolean | undefined) => {
      TagsUtils.setKaleCellTags(notebook, activeCellIndex, {
        stepName: stepName || '',
        prevStepNames: stepDependencies,
        limits: limits || {},
        secrets: secrets || {},
        baseImage,
        enableCaching: value,
        generateHtmlReport,
      });
    },
    [
      notebook,
      activeCellIndex,
      stepName,
      stepDependencies,
      limits,
      secrets,
      baseImage,
      generateHtmlReport,
    ],
  );

  const updateHtmlReport = useCallback(
    (value: boolean | undefined) => {
      TagsUtils.setKaleCellTags(notebook, activeCellIndex, {
        stepName: stepName || '',
        prevStepNames: stepDependencies,
        limits: limits || {},
        secrets: secrets || {},
        baseImage,
        enableCaching,
        generateHtmlReport: value,
      });
    },
    [
      notebook,
      activeCellIndex,
      stepName,
      stepDependencies,
      limits,
      secrets,
      baseImage,
      enableCaching,
    ],
  );

  const clearCellMetadata = useCallback(() => {
    TagsUtils.removeAllKaleTags(notebook, activeCellIndex);
  }, [notebook, activeCellIndex]);

  return {
    updateCellType,
    updateStepName,
    updateNotebookPath,
    updateDependencies,
    updateLimits,
    updateSecrets,
    updateBaseImage,
    updateCaching,
    updateHtmlReport,
    clearCellMetadata,
  };
}
