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

const DEFAULT_MEMORY_LIMIT = '2Gi';
// The memory quantities KFP accepts in `set_memory_limit()`.
const MEMORY_LIMIT_PATTERN = '^[0-9]+(E|Ei|P|Pi|T|Ti|G|Gi|M|Mi|K|Ki)?$';
const MEMORY_LIMIT_ERROR_MSG =
  'Use a whole number with an optional unit, e.g. 512Mi or 2Gi.';

export const isValidMemoryLimit = (value: string): boolean =>
  new RegExp(MEMORY_LIMIT_PATTERN).test(value);

interface IMemorySectionProps {
  stepName: string;
  limits: { [id: string]: string };
  updateLimits: (actions: ILimitAction[]) => void;
}

export const MemorySection: React.FC<IMemorySectionProps> = ({
  stepName,
  limits,
  updateLimits,
}) => {
  const memoryLimit = limits['memory'];
  const hasMemoryLimit = memoryLimit !== undefined;

  // What the user is typing. Only valid values are written to the cell tags,
  // so the field can be cleared and retyped without turning the limit off.
  const [inputValue, setInputValue] = React.useState(
    memoryLimit ?? DEFAULT_MEMORY_LIMIT,
  );
  // Follow the tags when they change outside the field (e.g. the toggle).
  React.useEffect(() => {
    setInputValue(memoryLimit ?? DEFAULT_MEMORY_LIMIT);
  }, [memoryLimit]);

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
            <p>Set Memory Limit for step </p>
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
              checked={hasMemoryLimit}
              onChange={c => {
                if (c.target.checked) {
                  updateLimits([
                    limitAction('update', 'memory', DEFAULT_MEMORY_LIMIT),
                  ]);
                } else {
                  updateLimits([limitAction('delete', 'memory')]);
                }
              }}
              color="primary"
              name="enableMemoryLimit"
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
            disabled={!hasMemoryLimit}
            variant="outlined"
            label="Memory Limit (e.g., 2Gi)"
            sx={disabledFieldSx}
            value={inputValue}
            regex={MEMORY_LIMIT_PATTERN}
            regexErrorMsg={MEMORY_LIMIT_ERROR_MSG}
            helperText={
              hasMemoryLimit && inputValue === ''
                ? 'Enter a memory limit, e.g. 2Gi.'
                : undefined
            }
            updateValue={(v: string) => {
              setInputValue(v);
              if (hasMemoryLimit && isValidMemoryLimit(v)) {
                updateLimits([limitAction('update', 'memory', v)]);
              }
            }}
            style={{ width: '95%' }}
          />
        </Grid>
      </Grid>
    </>
  );
};
