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
import { Box, Chip, Grid, Switch } from '@mui/material';
import ColorUtils from '../../../../lib/ColorUtils';
import { Input } from '../../../../components/Input';
import { Select } from '../../../../components/Select';
import { disabledFieldSx, ILimitAction, limitAction } from './limits';

const GPU_TYPES = [
  { value: 'nvidia.com/gpu', label: 'Nvidia' },
  { value: 'amd.com/gpu', label: 'AMD' },
];
const DEFAULT_GPU_TYPE = GPU_TYPES[0].value;
const DEFAULT_GPU_COUNT = '1';
const GPU_COUNT_PATTERN = '^[1-9][0-9]*$';
const isValidGpuCount = (value: string): boolean =>
  new RegExp(GPU_COUNT_PATTERN).test(value);

/** The GPU type requested in `limits`, if any. Assumes there is at most one. */
export const getGpuType = (limits: {
  [id: string]: string;
}): string | undefined =>
  Object.keys(limits).find(key => GPU_TYPES.some(t => t.value === key));

interface IGpuSectionProps {
  stepName: string;
  limits: { [id: string]: string };
  updateLimits: (actions: ILimitAction[]) => void;
}

export const GpuSection: React.FC<IGpuSectionProps> = ({
  stepName,
  limits,
  updateLimits,
}) => {
  const gpuType = getGpuType(limits);
  const gpuCount = gpuType && limits[gpuType];

  // What the user is typing. Only valid counts are written to the cell tags,
  // so the field can be cleared and retyped without turning the GPU off.
  const [countValue, setCountValue] = React.useState(
    gpuCount || DEFAULT_GPU_COUNT,
  );
  // Follow the tags when they change outside the field (e.g. the toggle).
  React.useEffect(() => {
    setCountValue(gpuCount || DEFAULT_GPU_COUNT);
  }, [gpuCount]);

  return (
    <>
      <Grid
        container
        sx={{
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Grid size={{ xs: 9 }}>
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'row',
              justifyContent: 'flex-start',
              alignItems: 'center',
            }}
          >
            <p>Require GPU for step </p>
            <Chip
              className={'kale-chip'}
              style={{
                marginLeft: '10px',
                backgroundColor: `#${ColorUtils.getColor(stepName)}`,
              }}
              key={stepName}
              label={stepName}
            />
          </Box>
        </Grid>
        <Grid size={{ xs: 3 }}>
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'row',
              justifyContent: 'flex-end',
              alignItems: 'center',
            }}
          >
            <Switch
              checked={gpuType !== undefined}
              onChange={c => {
                if (c.target.checked) {
                  // default value
                  updateLimits([
                    limitAction('update', DEFAULT_GPU_TYPE, DEFAULT_GPU_COUNT),
                  ]);
                } else if (gpuType) {
                  updateLimits([limitAction('delete', gpuType)]);
                }
              }}
              color="primary"
              name="enableKale"
              inputProps={{ 'aria-label': 'primary checkbox' }}
              classes={{ root: 'material-switch' }}
            />
          </Box>
        </Grid>
      </Grid>
      <Grid
        container
        sx={{
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: '15px',
        }}
      >
        <Grid size={{ xs: 6 }}>
          <Input
            disabled={gpuType === undefined}
            variant="outlined"
            label="GPU Count"
            sx={disabledFieldSx}
            value={countValue}
            regex={GPU_COUNT_PATTERN}
            regexErrorMsg="Enter a whole number of GPUs, e.g. 1."
            helperText={
              gpuType && countValue === ''
                ? 'Enter the number of GPUs, e.g. 1.'
                : undefined
            }
            updateValue={(v: string) => {
              setCountValue(v);
              if (gpuType && isValidGpuCount(v)) {
                updateLimits([limitAction('update', gpuType, v)]);
              }
            }}
            style={{ width: '95%' }}
          />
        </Grid>
        <Grid size={{ xs: 6 }}>
          <Select
            disabled={gpuType === undefined}
            sx={disabledFieldSx}
            updateValue={(v: string) => {
              const actions = [];
              if (gpuType) {
                actions.push(limitAction('delete', gpuType));
              }
              actions.push(limitAction('update', v, gpuCount));
              updateLimits(actions);
            }}
            values={GPU_TYPES}
            value={gpuType || DEFAULT_GPU_TYPE}
            label="GPU Type"
            index={0}
            variant="outlined"
          />
        </Grid>
      </Grid>
    </>
  );
};
