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
import { Input } from './Input';
import { Select, ISelectOption } from './Select';
import { IExperiment, NEW_EXPERIMENT } from '../widgets/LeftPanel';
import { EXPERIMENT_NAME_MAX_LENGTH } from '../widgets/LeftPanelTypes';

// KFP accepts any non-empty experiment name (see EXPERIMENT_NAME_MAX_LENGTH).
const regex: string = '\\S';
const regexErrorMsg: string = 'Experiment name cannot be only spaces.';

interface IExperimentInput {
  updateValue: (experiment: IExperiment) => void;
  options: IExperiment[];
  selected: string; // Experiment ID
  value: string; // Experiment Name
  loading: boolean;
}

export const ExperimentInput: React.FunctionComponent<
  IExperimentInput
> = props => {
  const getName = (x: string): string => {
    const filtered = props.options.filter(o => o.id === x);
    return filtered.length === 0 ? '' : filtered[0].name;
  };

  const updateSelected = (selected: string, index?: number) => {
    const value = selected === NEW_EXPERIMENT.id ? '' : getName(selected);
    const experiment: IExperiment = { id: selected, name: value };
    props.updateValue(experiment);
  };

  const updateValue = (value: string, index?: number) => {
    const experiment: IExperiment = { name: value, id: NEW_EXPERIMENT.id };
    props.updateValue(experiment);
  };

  const options: ISelectOption[] = props.options.map(o => ({
    label: o.name,
    value: o.id,
  }));

  return (
    <div>
      <Select
        variant="standard"
        label="Select experiment"
        values={options}
        value={props.selected}
        index={-1}
        updateValue={updateSelected}
        helperText={props.loading ? 'Loading...' : null}
      />
      {props.selected === NEW_EXPERIMENT.id && (
        <div>
          <Input
            updateValue={updateValue}
            value={props.value}
            label="Experiment Name"
            regex={regex}
            regexErrorMsg={regexErrorMsg}
            maxLength={EXPERIMENT_NAME_MAX_LENGTH}
            maxLengthErrorMsg={`Experiment name must be ${EXPERIMENT_NAME_MAX_LENGTH} characters or fewer.`}
            variant="standard"
            inputIndex={0}
          />
        </div>
      )}
    </div>
  );
};
