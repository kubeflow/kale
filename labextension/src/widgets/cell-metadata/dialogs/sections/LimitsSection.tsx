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
import { Box, Chip, Divider } from '@mui/material';
import ColorUtils from '../../../../lib/ColorUtils';
import { Select } from '../../../../components/Select';
import {
  disabledFieldSx,
  getGpuType,
  GPU_TYPES,
  ILimitAction,
  limitAction,
} from './limits';
import { ResourceLimit } from './ResourceLimit';

const DEFAULT_CPU_LIMIT = '1';
const DEFAULT_MEMORY_LIMIT = '2Gi';
const DEFAULT_GPU_TYPE = GPU_TYPES[0].value;
const DEFAULT_GPU_COUNT = '1';

// CPU quantities supported by KFP's `set_cpu_limit()`, such as `500m`, `2`,
// or `0.5`.
const CPU_LIMIT_PATTERN = '^[0-9]+(?:\\.[0-9]+)?m?$';
// The memory quantities KFP accepts in `set_memory_limit()`.
const MEMORY_LIMIT_PATTERN = '^[0-9]+(E|Ei|P|Pi|T|Ti|G|Gi|M|Mi|K|Ki)?$';
const GPU_COUNT_PATTERN = '^[1-9][0-9]*$';

interface ILimitsSectionProps {
  stepName: string;
  limits: { [id: string]: string };
  updateLimits: (actions: ILimitAction[]) => void;
}

/** The step's CPU, memory and GPU limits, in a single tab. */
export const LimitsSection: React.FC<ILimitsSectionProps> = ({
  stepName,
  limits,
  updateLimits,
}) => {
  const gpuType = getGpuType(limits);
  const gpuCount = gpuType && limits[gpuType];

  // A limit that only takes a single tag, i.e. CPU and memory.
  const simpleLimitHandlers = (key: string, defaultValue: string) => ({
    onEnable: () => updateLimits([limitAction('update', key, defaultValue)]),
    onDisable: () => updateLimits([limitAction('delete', key)]),
    onChange: (v: string) => updateLimits([limitAction('update', key, v)]),
  });

  return (
    <>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          justifyContent: 'flex-start',
          alignItems: 'center',
          marginBottom: '10px',
        }}
      >
        <p>Set resource limits for step </p>
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
      <Divider sx={{ marginBottom: '10px' }} />
      <ResourceLimit
        title="CPU limit"
        switchName="enableCpuLimit"
        value={limits['cpu']}
        defaultValue={DEFAULT_CPU_LIMIT}
        inputLabel="CPU Limit (e.g., 500m)"
        pattern={CPU_LIMIT_PATTERN}
        patternErrorMsg="Use a number with an optional milli-CPU suffix, e.g. 500m or 2."
        emptyHelperText="Enter a CPU limit, e.g. 500m or 2."
        {...simpleLimitHandlers('cpu', DEFAULT_CPU_LIMIT)}
      />
      <ResourceLimit
        title="Memory limit"
        switchName="enableMemoryLimit"
        value={limits['memory']}
        defaultValue={DEFAULT_MEMORY_LIMIT}
        inputLabel="Memory Limit (e.g., 2Gi)"
        pattern={MEMORY_LIMIT_PATTERN}
        patternErrorMsg="Use a whole number with an optional unit, e.g. 512Mi or 2Gi."
        emptyHelperText="Enter a memory limit, e.g. 2Gi."
        {...simpleLimitHandlers('memory', DEFAULT_MEMORY_LIMIT)}
      />
      <ResourceLimit
        title="Require GPU"
        switchName="enableGpuLimit"
        value={gpuCount}
        defaultValue={DEFAULT_GPU_COUNT}
        inputLabel="GPU Count"
        pattern={GPU_COUNT_PATTERN}
        patternErrorMsg="Enter a whole number of GPUs, e.g. 1."
        emptyHelperText="Enter the number of GPUs, e.g. 1."
        onEnable={() =>
          updateLimits([
            limitAction('update', DEFAULT_GPU_TYPE, DEFAULT_GPU_COUNT),
          ])
        }
        onDisable={() =>
          gpuType && updateLimits([limitAction('delete', gpuType)])
        }
        onChange={v =>
          gpuType && updateLimits([limitAction('update', gpuType, v)])
        }
      >
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
      </ResourceLimit>
    </>
  );
};
