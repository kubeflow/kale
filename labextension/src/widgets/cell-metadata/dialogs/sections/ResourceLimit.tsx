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
import { Box, Grid, Switch } from '@mui/material';
import { Input } from '../../../../components/Input';
import { disabledFieldSx } from './limits';

interface IResourceLimitProps {
  title: string;
  // `name` of the toggle's input, used to find it in tests.
  switchName: string;
  // The limit's current value in the cell tags, undefined when it is off.
  value: string | undefined;
  defaultValue: string;
  inputLabel: string;
  pattern: string;
  patternErrorMsg: string;
  emptyHelperText: string;
  onEnable: () => void;
  onDisable: () => void;
  // Called only with values matching `pattern`.
  onChange: (value: string) => void;
  // Extra fields shown next to the value input (e.g. the GPU type).
  children?: React.ReactNode;
}

/**
 * A single resource limit: a toggle to turn it on/off and a validated input
 * for its value. Shared by the CPU, memory and GPU limits.
 */
export const ResourceLimit: React.FC<IResourceLimitProps> = ({
  title,
  switchName,
  value,
  defaultValue,
  inputLabel,
  pattern,
  patternErrorMsg,
  emptyHelperText,
  onEnable,
  onDisable,
  onChange,
  children,
}) => {
  const enabled = value !== undefined;

  // What the user is typing. Only valid values are written to the cell tags,
  // so the field can be cleared and retyped without turning the limit off.
  const [inputValue, setInputValue] = React.useState(value || defaultValue);
  // Follow the tags when they change outside the field (e.g. the toggle).
  React.useEffect(() => {
    setInputValue(value || defaultValue);
  }, [value, defaultValue]);

  return (
    <Box sx={{ marginBottom: '20px' }}>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <p>{title}</p>
        <Switch
          checked={enabled}
          onChange={c => (c.target.checked ? onEnable() : onDisable())}
          color="primary"
          name={switchName}
          inputProps={{ 'aria-label': title }}
          classes={{ root: 'material-switch' }}
        />
      </Box>
      <Grid
        container
        sx={{
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: '10px',
        }}
      >
        <Grid size={{ xs: 6 }}>
          <Input
            disabled={!enabled}
            variant="outlined"
            label={inputLabel}
            sx={disabledFieldSx}
            value={inputValue}
            regex={pattern}
            regexErrorMsg={patternErrorMsg}
            helperText={
              enabled && inputValue === '' ? emptyHelperText : undefined
            }
            updateValue={(v: string) => {
              setInputValue(v);
              if (enabled && new RegExp(pattern).test(v)) {
                onChange(v);
              }
            }}
            style={{ width: '95%' }}
          />
        </Grid>
        {children && <Grid size={{ xs: 6 }}>{children}</Grid>}
      </Grid>
    </Box>
  );
};
