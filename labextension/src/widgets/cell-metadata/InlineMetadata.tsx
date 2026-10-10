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
import { useContext, useEffect, useRef } from 'react';
import { Chip, Tooltip } from '@mui/material';
import ColorUtils from '../../lib/ColorUtils';
import {
  RESERVED_CELL_NAMES,
  RESERVED_CELL_NAMES_HELP_TEXT,
} from './CellMetadataEditor';
import EditIcon from '@mui/icons-material/Edit';
import { CellMetadataContext } from '../../lib/CellMetadataContext';
import { ISecretRef } from '../../lib/TagsUtils';
import { getRuntimeImageName, RuntimeImages } from '../../lib/runtimeImages';

interface IProps {
  stepName: string;
  previousStepName?: string;
  stepDependencies: string[];
  limits: { [id: string]: string };
  baseImage?: string;
  runtimeImages: RuntimeImages;
  enableCaching?: boolean;
  generateHtmlReport?: boolean;
  secrets?: { [envName: string]: ISecretRef };
  cellElement: any;
  cellIndex: number;
  resolvedDefaultBaseImage: string;
}

function isDOMElement(obj: any): obj is HTMLElement {
  return (
    obj &&
    typeof obj === 'object' &&
    obj.nodeType === 1 &&
    typeof obj.classList !== 'undefined' &&
    typeof obj.querySelector === 'function'
  );
}

/**
 * This component is used by InlineCellsMetadata to display some state information
 * on top of each cell that is tagged with Kale tags.
 *
 * When a cell is tagged with a step name and some dependencies, a chip with the
 * step name and a series of coloured dots for its dependencies are show.
 */
export const InlineMetadata: React.FC<IProps> = ({
  stepName,
  previousStepName,
  stepDependencies,
  limits,
  baseImage,
  runtimeImages,
  enableCaching,
  generateHtmlReport,
  secrets,
  cellElement,
  cellIndex,
  resolvedDefaultBaseImage,
}) => {
  const context = useContext(CellMetadataContext);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const isMergedCell = !stepName;
  const isReserved = RESERVED_CELL_NAMES.includes(stepName);
  const isNotebookRef = stepName.startsWith('notebook:');
  const notebookRefName = isNotebookRef
    ? stepName.replace('notebook:', '')
    : '';
  const cellTypeClass = isReserved ? 'kale-reserved-cell' : '';
  const name = stepName || previousStepName;
  const color = name ? ColorUtils.getColor(name) : '';
  const showEditor =
    context.isEditorVisible && context.activeCellIndex === cellIndex;

  const dependencies = stepDependencies.map((depName, i) => {
    const rgb = ColorUtils.getColor(depName);
    return (
      <Tooltip placement="top" key={i} title={depName}>
        <div
          className="kale-inline-cell-dependency"
          style={{ backgroundColor: `#${rgb}` }}
        />
      </Tooltip>
    );
  });

  useEffect(() => {
    if (!isDOMElement(cellElement)) {
      return;
    }
    if (isMergedCell) {
      cellElement.classList.add('kale-merged-cell');
    } else {
      cellElement.classList.remove('kale-merged-cell');
    }
  }, [cellElement, isMergedCell]);

  useEffect(() => {
    if (!isDOMElement(cellElement)) {
      return;
    }
    const codeMirrorElem = cellElement.querySelector(
      '.CodeMirror',
    ) as HTMLElement;
    if (codeMirrorElem) {
      codeMirrorElem.style.borderLeft = color
        ? `2px solid #${color}`
        : '2px solid transparent';
    }
  }, [cellElement, color]);

  useEffect(() => {
    return () => {
      if (isDOMElement(cellElement)) {
        cellElement.classList.remove('kale-merged-cell');
        const codeMirrorElem = cellElement.querySelector(
          '.CodeMirror',
        ) as HTMLElement;
        if (codeMirrorElem) {
          codeMirrorElem.style.border = '';
        }
      }
      if (wrapperRef.current) {
        wrapperRef.current.remove();
      }
    };
  }, [cellElement]);

  const openEditor = () => {
    context.onEditorVisibilityChange(true);
  };

  const gpuType = Object.keys(limits)[0] || undefined;
  const limitsText = gpuType ? (
    <p style={{ fontStyle: 'italic', marginLeft: '10px' }}>
      GPU request: {gpuType + ' - '}
      {limits[gpuType]}
    </p>
  ) : null;

  const baseImageName = baseImage
    ? getRuntimeImageName(runtimeImages, baseImage)
    : undefined;
  const baseImageText = baseImage ? (
    <p className="kale-inline-base-image">
      <span className="kale-inline-base-image-label">Base Image:</span>
      <span
        className={`kale-inline-base-image-details${baseImageName ? ' has-name' : ''}`}
      >
        {baseImageName && (
          <>
            <strong
              className="kale-inline-base-image-name"
              title={baseImageName}
            >
              {baseImageName}
            </strong>
            <span className="kale-inline-base-image-separator">·</span>
          </>
        )}
        <span className="kale-inline-base-image-reference" title={baseImage}>
          {baseImage}
        </span>
      </span>
    </p>
  ) : null;

  const cacheText =
    enableCaching !== undefined ? (
      <p style={{ fontStyle: 'italic', marginLeft: '10px' }}>
        Cache: {enableCaching ? 'enabled' : 'disabled'}
      </p>
    ) : null;

  const reportText =
    generateHtmlReport === false ? (
      <p style={{ fontStyle: 'italic', marginLeft: '10px' }}>
        HTML Report: disabled
      </p>
    ) : null;

  const secretEnvNames = Object.keys(secrets || {});
  const secretsText =
    secretEnvNames.length > 0 ? (
      <p style={{ fontStyle: 'italic', marginLeft: '10px' }}>
        Secrets: {secretEnvNames.join(', ')}
      </p>
    ) : null;

  // a `notebook:` reference has no step details to show
  const details =
    isReserved || isNotebookRef ? null : (
      <>
        {dependencies.length > 0 ? (
          <p style={{ fontStyle: 'italic', margin: '0 5px' }}>depends on: </p>
        ) : null}
        {dependencies}
        {limitsText}
        {baseImageText}
        {cacheText}
        {reportText}
        {secretsText}
      </>
    );

  return (
    <div ref={wrapperRef} className={'kale-inline-cell-metadata-container'}>
      <div
        className={
          'kale-inline-cell-metadata' + (isMergedCell ? ' hidden' : '')
        }
      >
        {isReserved ? (
          ''
        ) : (
          <p style={{ fontStyle: 'italic', marginRight: '5px' }}>
            {isNotebookRef ? 'notebook: ' : 'step: '}
          </p>
        )}

        <Tooltip
          placement="top"
          key={stepName + 'tooltip'}
          title={
            isReserved
              ? RESERVED_CELL_NAMES_HELP_TEXT[stepName]
              : isNotebookRef
                ? 'This cell references another notebook as a sub-pipeline: ' +
                  notebookRefName
                : 'This cell starts the pipeline step: ' + stepName
          }
        >
          <Chip
            className={`kale-chip ${cellTypeClass}`}
            style={{ backgroundColor: `#${color}` }}
            key={stepName}
            label={isNotebookRef ? notebookRefName : stepName}
          />
        </Tooltip>

        {details}
      </div>

      <div
        className={'kale-editor-toggle-parent' + (showEditor ? ' hidden' : '')}
      >
        <button className="kale-editor-toggle" onClick={openEditor}>
          <EditIcon />
        </button>
      </div>
    </div>
  );
};
