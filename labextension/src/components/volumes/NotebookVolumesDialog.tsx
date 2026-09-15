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
import { useCallback, useEffect, useState } from 'react';
import { NotebookPanel } from '@jupyterlab/notebook';
import { Kernel } from '@jupyterlab/services';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import IconButton from '@mui/material/IconButton';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import CloseIcon from '@mui/icons-material/Close';
import { IVolumeConfig } from '../../widgets/LeftPanelTypes';
import Commands from '../../lib/Commands';
import {
  deriveEnvVarName,
  formatAccessModes,
  INotebookVolume,
} from './volumeUtils';

interface INotebookVolumesDialogProps {
  open: boolean;
  notebook: NotebookPanel | null;
  kernel: Kernel.IKernelConnection;
  onClose: () => void;
  onAdd: (volumes: IVolumeConfig[]) => void;
}

export const NotebookVolumesDialog: React.FC<INotebookVolumesDialogProps> = ({
  open,
  notebook,
  kernel,
  onClose,
  onAdd,
}) => {
  const [notebookVolumes, setNotebookVolumes] = useState<INotebookVolume[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [envVarSet, setEnvVarSet] = useState<Set<string>>(new Set());

  const getCommands = useCallback(
    () => (notebook ? new Commands(notebook, kernel) : null),
    [notebook, kernel],
  );

  useEffect(() => {
    if (!open) {
      return;
    }
    const cmds = getCommands();
    if (!cmds) {
      return;
    }
    setLoading(true);
    setSelected(new Set());
    setEnvVarSet(new Set());
    cmds
      .listNotebookVolumes()
      .then(vols => setNotebookVolumes(vols))
      .catch(() => setNotebookVolumes([]))
      .finally(() => setLoading(false));
  }, [open, getCommands]);

  const toggleVolume = (name: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  const toggleEnvVar = (name: string) => {
    setEnvVarSet(prev => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  const selectAll = () => {
    setSelected(new Set(notebookVolumes.map(v => v.name)));
  };

  const handleAdd = () => {
    const entries: IVolumeConfig[] = notebookVolumes
      .filter(v => selected.has(v.name))
      .map(v => ({
        name: v.name,
        mount_point: v.mount_point,
        type: 'pvc' as const,
        expose_as_env_var: envVarSet.has(v.name),
      }));
    onAdd(entries);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>
        Select volumes from notebook pod
        <IconButton
          size="small"
          onClick={onClose}
          sx={{ position: 'absolute', right: 8, top: 8 }}
          aria-label="Close"
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers>
        {loading ? (
          <div className="kale-dialog-loading">
            <CircularProgress size={24} />
          </div>
        ) : notebookVolumes.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No volumes found on the notebook pod.
          </Typography>
        ) : (
          <>
            <Button
              size="small"
              onClick={selectAll}
              disabled={selected.size === notebookVolumes.length}
              sx={{ mb: 1 }}
            >
              Select all
            </Button>
            <List dense disablePadding>
              {notebookVolumes.map(vol => {
                const modes = formatAccessModes(vol.access_modes);
                return (
                  <ListItem
                    key={vol.name}
                    disableGutters
                    className="kale-nb-volume-item"
                  >
                    <Checkbox
                      size="small"
                      checked={selected.has(vol.name)}
                      onChange={() => toggleVolume(vol.name)}
                    />
                    <span className="kale-nb-volume-label">
                      <span className="kale-nb-volume-name">
                        {vol.name}
                        {modes && (
                          <span className="kale-pvc-access-mode">{modes}</span>
                        )}
                      </span>
                      <span className="kale-nb-volume-mount">
                        {vol.mount_point || '(specify mount path)'}
                      </span>
                    </span>
                    <Tooltip
                      title={
                        selected.has(vol.name)
                          ? `Expose as ${deriveEnvVarName(vol.name)}`
                          : 'Select this volume first to expose as env var'
                      }
                    >
                      <span>
                        <Checkbox
                          size="small"
                          icon={<span className="kale-envvar-icon">env</span>}
                          checkedIcon={
                            <span className="kale-envvar-icon kale-envvar-icon-checked">
                              env
                            </span>
                          }
                          checked={envVarSet.has(vol.name)}
                          disabled={!selected.has(vol.name)}
                          onChange={() => toggleEnvVar(vol.name)}
                          aria-label={`Expose ${vol.name} as env var`}
                        />
                      </span>
                    </Tooltip>
                  </ListItem>
                );
              })}
            </List>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ mt: 1, display: 'block' }}
            >
              env = expose mount path as env var (e.g. KALE_VOLUME_MY_DATA)
            </Typography>
          </>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleAdd}
          disabled={selected.size === 0}
        >
          Add selected
        </Button>
      </DialogActions>
    </Dialog>
  );
};
