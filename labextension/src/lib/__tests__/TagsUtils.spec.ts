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

import { CodeCellModel } from '@jupyterlab/cells';
import { NotebookPanel } from '@jupyterlab/notebook';

import TagsUtils from '../TagsUtils';
import {
  CELL_TYPES,
  KALE_TAG_PREFIXES,
} from '../../widgets/cell-metadata/constants';

/**
 * A NotebookPanel is far more than these tests need: the code under test only
 * reaches `model.cells.get(index)` and then the cell's own metadata API. So
 * wrap real CodeCellModels — whose metadata behaves like the real thing — in
 * the smallest object that satisfies both call sites.
 */
function notebookWith(cells: CodeCellModel[]): NotebookPanel {
  const panel = {
    model: { cells: { length: cells.length, get: (i: number) => cells[i] } },
  };
  // `content` is the Notebook widget; the reads in CellUtils only need `model`.
  (panel as any).content = panel;
  return panel as unknown as NotebookPanel;
}

function referenceCell(): CodeCellModel {
  const cell = new CodeCellModel({});
  cell.setMetadata('tags', ['notebook:other', 'prev:load']);
  cell.setMetadata('notebook_path', 'examples/composition/notebook_a.ipynb');
  return cell;
}

describe('TagsUtils.removeAllKaleTags', () => {
  it('removes the notebook: tag from a reference cell', () => {
    const cell = referenceCell();
    TagsUtils.removeAllKaleTags(notebookWith([cell]), 0);
    expect(cell.getMetadata('tags')).toEqual([]);
  });

  it('removes the notebook_path metadata along with the tag', () => {
    const cell = referenceCell();
    TagsUtils.removeAllKaleTags(notebookWith([cell]), 0);
    expect(cell.getMetadata('notebook_path')).toBeUndefined();
  });

  it('leaves tags that do not belong to Kale alone', () => {
    const cell = new CodeCellModel({});
    cell.setMetadata('tags', ['notebook:other', 'my-own-tag']);
    TagsUtils.removeAllKaleTags(notebookWith([cell]), 0);
    expect(cell.getMetadata('tags')).toEqual(['my-own-tag']);
  });

  it('is a no-op on a cell that was never a reference', () => {
    const cell = new CodeCellModel({});
    cell.setMetadata('tags', ['my-own-tag']);
    TagsUtils.removeAllKaleTags(notebookWith([cell]), 0);
    expect(cell.getMetadata('tags')).toEqual(['my-own-tag']);
    expect(cell.getMetadata('notebook_path')).toBeUndefined();
  });
});

describe('KALE_TAG_PREFIXES', () => {
  /**
   * The bug this file was written for: `notebook` was added to CELL_TYPES
   * without the matching prefix, so clearing a reference cell left its tag
   * behind. Assert the two lists agree, so the next cell type cannot repeat it.
   */
  it('covers every cell type that writes a tag', () => {
    const uncovered = CELL_TYPES.map(t => t.value).filter(
      value =>
        !KALE_TAG_PREFIXES.some(
          prefix => prefix === value || prefix === `${value}:`,
        ),
    );
    expect(uncovered).toEqual([]);
  });
});
