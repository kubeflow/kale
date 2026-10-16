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

export interface ILimitAction {
  action: 'update' | 'delete';
  limitKey: string;
  limitValue?: string;
}

// Scoped to this section: the shared Input/Select components don't have a
// dark-mode-aware disabled style, so override it here rather than in the
// shared components (which are used well beyond this dialog).
const disabledFieldSx = {
  '& .MuiInputBase-input.Mui-disabled': {
    WebkitTextFillColor: 'var(--jp-ui-font-color2)',
  },
  '& .MuiInputLabel-root': {
    color: 'var(--jp-ui-font-color2)',
  },
  '& .MuiOutlinedInput-notchedOutline': {
    borderColor: 'var(--jp-input-border-color)',
  },
};

const GPU_TYPES = [
  { value: 'nvidia.com/gpu', label: 'Nvidia' },
  { value: 'amd.com/gpu', label: 'AMD' },
];
const DEFAULT_GPU_TYPE = GPU_TYPES[0].value;

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
  const limitAction = (
    action: ILimitAction['action'],
    limitKey: ILimitAction['limitKey'],
    limitValue: ILimitAction['limitValue'] = undefined,
  ) => ({ action, limitKey, limitValue });

  const gpuType = getGpuType(limits);
  const gpuCount = gpuType && limits[gpuType];

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
                  updateLimits([limitAction('update', DEFAULT_GPU_TYPE, '1')]);
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
            value={gpuCount || 1}
            updateValue={(v: string) => {
              if (gpuType) {
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
