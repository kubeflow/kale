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
import { disabledFieldSx, ILimitAction, limitAction } from './limits';

const DEFAULT_CPU_LIMIT = '1';
// CPU quantities supported by KFP's `set_cpu_limit()`, such as `500m`, `2`,
// or `0.5`.
const CPU_LIMIT_PATTERN = '^[0-9]+(?:\\.[0-9]+)?m?$';
const CPU_LIMIT_ERROR_MSG =
  'Use a number with an optional milli-CPU suffix, e.g. 500m or 2.';

export const isValidCpuLimit = (value: string): boolean =>
  new RegExp(CPU_LIMIT_PATTERN).test(value);

interface ICpuSectionProps {
  stepName: string;
  limits: { [id: string]: string };
  updateLimits: (actions: ILimitAction[]) => void;
}

export const CpuSection: React.FC<ICpuSectionProps> = ({
  stepName,
  limits,
  updateLimits,
}) => {
  const cpuLimit = limits['cpu'];
  const hasCpuLimit = cpuLimit !== undefined;
  const [inputValue, setInputValue] = React.useState(
    cpuLimit ?? DEFAULT_CPU_LIMIT,
  );

  React.useEffect(() => {
    setInputValue(cpuLimit ?? DEFAULT_CPU_LIMIT);
  }, [cpuLimit]);

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
            <p>Set CPU Limit for step </p>
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
              checked={hasCpuLimit}
              onChange={c => {
                if (c.target.checked) {
                  updateLimits([
                    limitAction('update', 'cpu', DEFAULT_CPU_LIMIT),
                  ]);
                } else {
                  updateLimits([limitAction('delete', 'cpu')]);
                }
              }}
              color="primary"
              name="enableCpuLimit"
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
            disabled={!hasCpuLimit}
            variant="outlined"
            label="CPU Limit (e.g., 500m)"
            sx={disabledFieldSx}
            value={inputValue}
            regex={CPU_LIMIT_PATTERN}
            regexErrorMsg={CPU_LIMIT_ERROR_MSG}
            helperText={
              hasCpuLimit && inputValue === ''
                ? 'Enter a CPU limit, e.g. 500m or 2.'
                : undefined
            }
            updateValue={(v: string) => {
              setInputValue(v);
              if (hasCpuLimit && isValidCpuLimit(v)) {
                updateLimits([limitAction('update', 'cpu', v)]);
              }
            }}
            style={{ width: '95%' }}
          />
        </Grid>
      </Grid>
    </>
  );
};
