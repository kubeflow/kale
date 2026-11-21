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
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import CloseIcon from '@mui/icons-material/Close';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import EditIcon from '@mui/icons-material/Edit';
import StorageIcon from '@mui/icons-material/Storage';
import { IVolumeConfig } from '../../widgets/LeftPanelTypes';
import { deriveEnvVarName, formatAccessModes } from './volumeUtils';

interface IVolumeRowProps {
  vol: IVolumeConfig;
  accessModes?: string[];
  isDupMount: boolean;
  isDupEnvVar: boolean;
  copiedEnvVar: string | null;
  onEdit: () => void;
  onRemove: () => void;
  onCopyEnvVar: (name: string) => void;
}

export const VolumeRow: React.FC<IVolumeRowProps> = ({
  vol,
  accessModes,
  isDupMount,
  isDupEnvVar,
  copiedEnvVar,
  onEdit,
  onRemove,
  onCopyEnvVar,
}) => {
  const envVarName = deriveEnvVarName(vol.name);
  const modesLabel = formatAccessModes(accessModes);

  return (
    <div className="kale-volume-row">
      <div className="kale-volume-row-header">
        <StorageIcon fontSize="small" className="kale-volume-icon" />
        <span className="kale-volume-name" title={vol.name}>
          {vol.name}
          {modesLabel && (
            <span className="kale-pvc-access-mode">{modesLabel}</span>
          )}
        </span>
        <span className="kale-volume-mount" title={vol.mount_point}>
          {vol.mount_point}
        </span>
        <Tooltip title="Edit volume">
          <IconButton
            size="small"
            className="kale-volume-edit-btn"
            onClick={onEdit}
            aria-label={`Edit ${vol.name}`}
          >
            <EditIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Remove volume">
          <IconButton
            size="small"
            className="kale-volume-remove-btn"
            onClick={onRemove}
            aria-label={`Remove ${vol.name}`}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </div>

      {isDupMount && (
        <Typography variant="caption" className="kale-volume-warning">
          Duplicate mount path "{vol.mount_point}"
        </Typography>
      )}
      {isDupEnvVar && (
        <Typography variant="caption" className="kale-volume-warning">
          Duplicate env var "{envVarName}"
        </Typography>
      )}
      {vol.expose_as_env_var && (
        <div className="kale-volume-envvar-row">
          <Typography variant="caption" className="kale-volume-envvar-label">
            {envVarName}
          </Typography>
          <Tooltip
            title={
              copiedEnvVar === envVarName ? 'Copied!' : 'Copy env var name'
            }
          >
            <IconButton
              size="small"
              onClick={() => onCopyEnvVar(envVarName)}
              aria-label="Copy env var name"
              className="kale-volume-copy-btn"
            >
              <ContentCopyIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
        </div>
      )}
    </div>
  );
};
