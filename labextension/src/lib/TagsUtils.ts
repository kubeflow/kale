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

import { Notebook, NotebookPanel } from '@jupyterlab/notebook';
import CellUtils from './CellUtils';
import { RESERVED_CELL_NAMES } from '../widgets/cell-metadata/CellMetadataEditor';
import { KALE_TAG_PREFIXES } from '../widgets/cell-metadata/constants';

const IMAGE_TAG = 'image:';
const CACHE_TAG = 'cache:';
const SECRET_TAG = 'secret:';
const CACHE_ENABLED_VALUE = 'enabled';
const REPORT_TAG = 'report:';
const REPORT_ENABLED_VALUE = 'enabled';

export interface ISecretRef {
  secretName: string;
  secretKey: string;
}

const NOTEBOOK_PREFIX = 'notebook:';

interface IKaleCellTags {
  stepName: string;
  prevStepNames: string[];
  limits?: { [id: string]: string };
  secrets?: { [envName: string]: ISecretRef };
  baseImage?: string;
  enableCaching?: boolean;
  // set when the cell is a `notebook:` reference (stepName = 'notebook:<name>')
  notebookPath?: string;
  generateHtmlReport?: boolean;
}

/** Contains utility functions for manipulating/handling Kale cell tags. */
export default class TagsUtils {
  /**
   * Get all the `step:<name>` tags in the notebook.
   * @param notebook Notebook object
   * @returns Array<str> - a list of the pipeline step names
   */
  public static getAllSteps(notebook: Notebook, cellIndex: number = -1): string[] {
    if (!notebook.model) {
      return [];
    }
    const steps = new Set<string>();
    const toCell = cellIndex < 0 ? notebook.model.cells.length : cellIndex;
    // iterate through the notebook cells
    for (const idx of Array(toCell).keys()) {
      // get the tags of the current cell
      const mt = this.getKaleCellTags(notebook, idx);
      if (
        mt &&
        mt.stepName &&
        mt.stepName !== '' &&
        // notebook references are not steps: they cannot be `prev:` targets
        !mt.stepName.startsWith(NOTEBOOK_PREFIX)
      ) {
        steps.add(mt.stepName);
      }
    }
    return Array.from(steps);
  }

  /**
   * Given a notebook cell index, get the closest previous cell that has a Kale
   * tag
   * @param notebook The notebook object
   * @param current The index of the cell to start the search from
   * @returns string - Name of the `step` tag of the closest previous cell
   */
  public static getPreviousStep(notebook: Notebook, current: number): string | undefined {
    for (let i = current - 1; i >= 0; i--) {
      const mt = this.getKaleCellTags(notebook, i);
      // a `notebook:` reference breaks the merge chain: untagged cells after it
      // belong to the NEXT step, never to a step above the reference
      if (mt && mt.stepName.startsWith(NOTEBOOK_PREFIX)) {
        return undefined;
      }
      if (
        mt &&
        mt.stepName &&
        mt.stepName !== 'skip' &&
        mt.stepName !== ''
      ) {
        return mt.stepName;
      }
    }
    return undefined;
  }

  /**
   * Parse a notebook cell's metadata and return all the Kale tags
   * @param notebook Notebook object
   * @param index The index of the notebook cell
   * @returns IKaleCellTags: an object containing all the cell's Kale tags
   */
  public static getKaleCellTags(
    notebook: Notebook,
    index: number,
  ): IKaleCellTags | null {
    const tags: string[] = CellUtils.getCellMetaData(notebook, index, 'tags') || [];
    if (tags) {
      const b_name = tags.map(v => {
        if (RESERVED_CELL_NAMES.includes(v)) {
          return v;
        }
        // a `notebook:<name>` reference is kept whole, so that the cell type
        // can be told apart from a step by its prefix
        if (v.startsWith(NOTEBOOK_PREFIX)) {
          return v;
        }
        if (v.startsWith('step:')) {
          return v.replace('step:', '');
        }
      }).filter(v => v !== undefined);

      const prevs = tags
        .filter(v => {
          return v.startsWith('prev:');
        })
        .map(v => {
          return v.replace('prev:', '');
        });

      const limits: { [id: string]: string } = {};
      tags
        .filter(v => v.startsWith('limit:'))
        .map(lim => {
          const values = lim.split(':');
          // get the limit key and value
          limits[values[1]] = values[2];
        });

      const secrets: { [envName: string]: ISecretRef } = {};
      tags
        .filter(v => v.startsWith(SECRET_TAG))
        .map(s => {
          const values = s.split(':');
          // secret:<secretName>:<secretKey>:<envName>
          secrets[values[3]] = { secretName: values[1], secretKey: values[2] };
        });

      // Parse base image tag
      let baseImage: string | undefined;
      const imageTag = tags.find(v => v.startsWith(IMAGE_TAG));
      if (imageTag) {
        // Remove 'image:' prefix to get the full image string
        baseImage = imageTag.substring(IMAGE_TAG.length);
      }

      // Parse cache tag
      let enableCaching: boolean | undefined;
      const cacheTag = tags.find(v => v.startsWith(CACHE_TAG));
      if (cacheTag) {
        const cacheValue = cacheTag.substring(CACHE_TAG.length);
        enableCaching = cacheValue === CACHE_ENABLED_VALUE ? true : false;
      }

      // Parse report tag
      let generateHtmlReport: boolean | undefined;
      const reportTag = tags.find(v => v.startsWith(REPORT_TAG));
      if (reportTag) {
        const reportValue = reportTag.substring(REPORT_TAG.length);
        generateHtmlReport = reportValue === REPORT_ENABLED_VALUE ? true : false;
      }

      const stepName = b_name[0] || '';
      let notebookPath: string | undefined;
      if (stepName.startsWith(NOTEBOOK_PREFIX)) {
        notebookPath =
          (CellUtils.getCellMetaData(
            notebook,
            index,
            'notebook_path',
          ) as unknown as string) || undefined;
      }

      return {
        stepName: stepName,
        prevStepNames: prevs,
        limits: limits,
        secrets: secrets,
        baseImage: baseImage,
        enableCaching: enableCaching,
        notebookPath: notebookPath,
        generateHtmlReport: generateHtmlReport,
      };
    }
    return null;
  }

  /**
   * Set the provided Kale metadata into the specified notebook cell
   * @param notebookPanel NotebookPanel object
   * @param index index of the target cell
   * @param metadata Kale metadata
   * @param save True to save the notebook after the operation
   */
  public static setKaleCellTags(
    notebookPanel: NotebookPanel,
    index: number,
    metadata: IKaleCellTags
  ): Promise<any> {
    // make the dict to save to tags
    let nb = metadata.stepName;
    // not a reserved name or a notebook reference (written as-is)
    if (
      !RESERVED_CELL_NAMES.includes(metadata.stepName) &&
      !metadata.stepName.startsWith(NOTEBOOK_PREFIX)
    ) {
      nb = 'step:' + nb;
    }
    const stepDependencies = metadata.prevStepNames || [];
    const limits = metadata.limits || {};
    const secrets = metadata.secrets || {};
    const baseImage = metadata.baseImage;
    const tags = [nb]
      .concat(stepDependencies.map(v => 'prev:' + v))
      .concat(
        Object.keys(limits).map(lim => 'limit:' + lim + ':' + limits[lim]),
      )
      .concat(
        Object.keys(secrets).map(
          env =>
            SECRET_TAG +
            secrets[env].secretName +
            ':' +
            secrets[env].secretKey +
            ':' +
            env,
        ),
      );

    // Add base image tag if specified
    if (baseImage) {
      tags.push(IMAGE_TAG + baseImage);
    }

    // Add cache tag if specified
    if (metadata.enableCaching !== undefined) {
      tags.push(CACHE_TAG + (metadata.enableCaching ? 'enabled' : 'disabled'));
    }

    // Add report tag if specified
    if (metadata.generateHtmlReport !== undefined) {
      tags.push(REPORT_TAG + (metadata.generateHtmlReport ? 'enabled' : 'disabled'));
    }

    // A notebook reference carries its target's path in the cell metadata
    // (`notebook_path`), which the backend resolves relative to this notebook.
    if (metadata.stepName.startsWith(NOTEBOOK_PREFIX)) {
      if (metadata.notebookPath !== undefined) {
        CellUtils.setCellMetaData(
          notebookPanel,
          index,
          'notebook_path',
          metadata.notebookPath,
        );
      }
    } else {
      // The cell is no longer a reference, so the path it pointed at is stale.
      // Drop it here, where the tag is rewritten, so the two cannot disagree
      // about whether this cell still references a notebook.
      CellUtils.deleteCellMetaData(notebookPanel, index, 'notebook_path');
    }

    return CellUtils.setCellMetaData(notebookPanel, index, 'tags', tags);
  }

  /**
   * Parse the entire notebook cells to change a step name. This happens when
   * the step name of a cell is changed by the user, using Kale's inline tag
   * editor. We need to parse the entire notebook because all the `prev` dependencies
   * specified in the cells must be bound to the new name.
   * @param notebookPanel NotebookPanel object
   * @param oldStepName previous step name
   * @param newStepName new step name
   */
  public static updateKaleCellsTags(
    notebookPanel: NotebookPanel,
    oldStepName: string,
    newStepName: string,
  ) {
    let i: number;
    const allPromises = [];
    for (i = 0; i < notebookPanel.model!.cells.length; i++) {
      const tags: string[] = CellUtils.getCellMetaData(
        notebookPanel.content,
        i,
        'tags',
      ) || [];
      // If there is a prev tag that points to the old name, update it with the
      // new one.
      const newTags: string[] = (tags || [])
        .map(t => {
          if (t === 'prev:' + oldStepName) {
            return RESERVED_CELL_NAMES.includes(newStepName)
              ? ''
              : 'prev:' + newStepName;
          } else {
            return t;
          }
        })
        .filter(t => t !== '' && t !== 'prev:');
      allPromises.push(
        CellUtils.setCellMetaData(notebookPanel, i, 'tags', newTags),
      );
    }
    Promise.all(allPromises);
  }

  /**
   * Clean up the Kale tags from a cell. After cleaning the cell, loop though
   * the notebook to remove all occurrences of the deleted step name.
   * @param notebook NotebookPanel object
   * @param activeCellIndex The active cell index
   * @param stepName The old name of the active cell to be cleaned.
   */
  public static resetCell(
    notebook: NotebookPanel,
    activeCellIndex: number,
    stepName: string,
  ) {
    const value = '';
    const previousSteps: string[] = [];

    const oldStepName: string = stepName;
    const cellMetadata = {
      prevStepNames: previousSteps,
      stepName: value,
    };
    TagsUtils.setKaleCellTags(
      notebook,
      activeCellIndex,
      cellMetadata
    ).then(oldValue => {
      TagsUtils.updateKaleCellsTags(notebook, oldStepName, value);
    });
  }
  public static removeAllKaleTags(
    notebook: NotebookPanel,
    activeCellIndex: number,
  ) {
    const currentTags: string[] =
      CellUtils.getCellMetaData(
        notebook.content,
        activeCellIndex,
        'tags',
      ) || [];

    // Extract the step name from 'step:<name>' tag before wiping
    const stepTag = currentTags.find(tag => tag.startsWith('step:'));
    const clearedStepName = stepTag ? stepTag.replace('step:', '') : null;

    // Clear all Kale tags from the active cell
    const filteredTags = currentTags.filter(
      tag => !KALE_TAG_PREFIXES.some(prefix => tag.startsWith(prefix)),
    );

    // `notebook_path` is not a tag, so the filter above cannot reach it.
    // Clearing a reference cell has to remove it too, or the cell reads as
    // cleared while still carrying the path it referenced.
    CellUtils.deleteCellMetaData(notebook, activeCellIndex, 'notebook_path');

    CellUtils.setCellMetaData(
      notebook,
      activeCellIndex,
      'tags',
      filteredTags,
    ).then(() => {
      // If this cell had a step name, remove all prev:<stepName> refs
      // from dependent cells using the existing updateKaleCellsTags
      if (clearedStepName) {
        TagsUtils.updateKaleCellsTags(notebook, clearedStepName, '');
      }
    });
  }

  public static cellsToArray(notebook: NotebookPanel) {
    const cells = notebook.model?.cells;
    const cellsArray = [];
    if (cells) {
      for (let index = 0; index < cells.length; index += 1) {
        const cell = cells.get(index);
        cellsArray.push(cell);
      }
    }
    return cellsArray;
  }

  public static removeOldDependencies(
    notebook: NotebookPanel
  ) {
    const cells = notebook.model?.cells;
    if (!cells) {
      return;
    }

    const allSteps = this.getAllSteps(notebook.content);
    const allStepsSet = new Set(allSteps);

    for (let index = 0; index < cells.length; index++) {
      const kaleTags = this.getKaleCellTags(notebook.content, index);
      if (!kaleTags) {
        continue;
      }

      const newPrevStepNames = kaleTags.prevStepNames.filter(
        dep => allStepsSet.has(dep)
      );

      if (newPrevStepNames.length !== kaleTags.prevStepNames.length) {
        const updatedMetadata = {
          ...kaleTags,
          prevStepNames: newPrevStepNames,
        };

        this.setKaleCellTags(notebook, index, updatedMetadata);
      }
    }

  }
}
