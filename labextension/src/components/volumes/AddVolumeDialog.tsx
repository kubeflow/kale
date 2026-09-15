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
import Autocomplete from '@mui/material/Autocomplete';
import Popper, { PopperProps } from '@mui/material/Popper';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControlLabel from '@mui/material/FormControlLabel';
import IconButton from '@mui/material/IconButton';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import CloseIcon from '@mui/icons-material/Close';
import { IVolumeConfig } from '../../widgets/LeftPanelTypes';
import Commands from '../../lib/Commands';
import {
  deriveEnvVarName,
  EMPTY_FORM,
  formatAccessModes,
  getMountPathError,
  IAddFormState,
  IPvcInfo,
} from './volumeUtils';
import { NotebookVolumesDialog } from './NotebookVolumesDialog';

// Renders the Autocomplete dropdown above the Dialog backdrop (z-index 1300).
function AboveDialogPopper(props: PopperProps) {
  return <Popper {...props} style={{ ...props.style, zIndex: 1400 }} />;
}

const helperTextSx = {
  '& .MuiFormHelperText-root': { color: 'var(--jp-info-color0)' },
};

interface IAddVolumeDialogProps {
  open: boolean;
  /** null = adding new volume, number = editing volume at that index */
  editingIdx: number | null;
  volumes: IVolumeConfig[];
  notebook: NotebookPanel | null;
  kernel: Kernel.IKernelConnection;
  onClose: () => void;
  onCommit: (entry: IVolumeConfig) => void;
  onAddMultiple: (entries: IVolumeConfig[]) => void;
}

export const AddVolumeDialog: React.FC<IAddVolumeDialogProps> = ({
  open,
  editingIdx,
  volumes,
  notebook,
  kernel,
  onClose,
  onCommit,
  onAddMultiple,
}) => {
  const [form, setForm] = useState<IAddFormState>(EMPTY_FORM);
  const [pvcSuggestions, setPvcSuggestions] = useState<IPvcInfo[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [showNotebookDialog, setShowNotebookDialog] = useState(false);

  // Helper to get PVC names for validation
  const pvcNames = pvcSuggestions.map(p => p.name);

  const getCommands = useCallback(
    () => (notebook ? new Commands(notebook, kernel) : null),
    [notebook, kernel],
  );

  // Initialise form when the dialog opens
  useEffect(() => {
    if (!open) {
      return;
    }
    if (editingIdx !== null) {
      const vol = volumes[editingIdx];
      setForm({
        name: vol.name,
        mount_point: vol.mount_point,
        expose_as_env_var: vol.expose_as_env_var ?? false,
      });
    } else {
      setForm(EMPTY_FORM);
    }
  }, [open, editingIdx, volumes]);

  // Fetch PVC suggestions when the dialog opens
  useEffect(() => {
    if (!open) {
      return;
    }
    const cmds = getCommands();
    if (!cmds) {
      return;
    }
    setLoadingSuggestions(true);
    cmds
      .listPvcs()
      .then(names => setPvcSuggestions(names))
      .catch(() => setPvcSuggestions([]))
      .finally(() => setLoadingSuggestions(false));
  }, [open, getCommands]);

  // Validation
  const nameDuplicate =
    form.name.trim() !== '' &&
    volumes.some((v, i) => v.name === form.name.trim() && i !== editingIdx);

  const mountPathError = getMountPathError(form.mount_point);

  const mountDuplicate =
    form.mount_point.trim() !== '' &&
    volumes.some(
      (v, i) => v.mount_point === form.mount_point.trim() && i !== editingIdx,
    );

  const derivedEnvVar =
    form.expose_as_env_var && form.name.trim()
      ? deriveEnvVarName(form.name.trim())
      : null;

  const envVarDuplicate =
    !!derivedEnvVar &&
    volumes.some(
      (v, i) =>
        i !== editingIdx &&
        v.expose_as_env_var &&
        deriveEnvVarName(v.name) === derivedEnvVar,
    );

  const pvcUnknown =
    form.name.trim() !== '' &&
    pvcNames.length > 0 &&
    !pvcNames.includes(form.name.trim());

  const canSubmit =
    form.name.trim() !== '' &&
    form.mount_point.trim() !== '' &&
    !nameDuplicate &&
    !mountPathError &&
    !mountDuplicate &&
    !envVarDuplicate;

  const handleCommit = () => {
    if (!canSubmit) {
      return;
    }
    onCommit({
      name: form.name.trim(),
      mount_point: form.mount_point.trim(),
      type: 'pvc',
      expose_as_env_var: form.expose_as_env_var,
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && canSubmit) {
      handleCommit();
    }
  };

  const handleNotebookAdd = (entries: IVolumeConfig[]) => {
    setShowNotebookDialog(false);
    onAddMultiple(entries);
  };

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        maxWidth="sm"
        fullWidth
        onKeyDown={handleKeyDown}
      >
        <DialogTitle>
          {editingIdx !== null ? 'Edit Volume' : 'Add Volume'}
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
          <div className="kale-add-volume-form">
            <Button
              variant="outlined"
              size="small"
              onClick={() => setShowNotebookDialog(true)}
              className="kale-select-from-notebook-btn"
              disabled={!notebook}
            >
              Select from notebook
            </Button>

            {/* PVC combobox — freeSolo lets users type any name;
                forcePopupIcon shows the arrow so it looks like a selectbox */}
            <Autocomplete
              freeSolo
              forcePopupIcon
              options={pvcSuggestions}
              getOptionLabel={opt => (typeof opt === 'string' ? opt : opt.name)}
              getOptionKey={opt => (typeof opt === 'string' ? opt : opt.name)}
              isOptionEqualToValue={(opt, val) =>
                (typeof opt === 'string' ? opt : opt.name) ===
                (typeof val === 'string' ? val : val.name)
              }
              value={form.name}
              loading={loadingSuggestions}
              loadingText="Loading PVCs…"
              noOptionsText="No PVCs found — type a name to use it directly"
              slots={{ popper: AboveDialogPopper }}
              onInputChange={(_e, value) =>
                setForm(prev => ({ ...prev, name: value }))
              }
              renderOption={(props, option) => {
                const { key, ...rest } = props;
                const isString = typeof option === 'string';
                const name = isString ? option : option.name;
                const modes = isString
                  ? ''
                  : formatAccessModes(option.access_modes);
                return (
                  <li key={key} {...rest}>
                    <span className="kale-pvc-option">
                      <span className="kale-pvc-name">{name}</span>
                      {modes && (
                        <span className="kale-pvc-access-mode">{modes}</span>
                      )}
                    </span>
                  </li>
                );
              }}
              renderInput={params => (
                <TextField
                  {...params}
                  label="PVC name"
                  variant="outlined"
                  size="small"
                  error={nameDuplicate || pvcUnknown}
                  sx={nameDuplicate || pvcUnknown ? undefined : helperTextSx}
                  helperText={
                    nameDuplicate
                      ? 'This volume name is already used by another volume'
                      : pvcUnknown
                        ? 'PVC not found in cluster — it will still be mounted at runtime'
                        : 'Type a name or pick from the list of available PVCs'
                  }
                  slotProps={{
                    input: {
                      ...params.InputProps,
                      endAdornment: (
                        <>
                          {loadingSuggestions ? (
                            <CircularProgress color="inherit" size={14} />
                          ) : null}
                          {params.InputProps.endAdornment}
                        </>
                      ),
                    },
                  }}
                />
              )}
            />

            <TextField
              label="Mount path"
              variant="outlined"
              size="small"
              fullWidth
              placeholder="/data"
              value={form.mount_point}
              onChange={e =>
                setForm(prev => ({ ...prev, mount_point: e.target.value }))
              }
              error={!!mountPathError || mountDuplicate}
              sx={mountPathError || mountDuplicate ? undefined : helperTextSx}
              helperText={
                mountPathError
                  ? mountPathError
                  : mountDuplicate
                    ? 'Mount path already used by another volume'
                    : 'Absolute path where the PVC will be mounted in each step pod'
              }
            />

            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={form.expose_as_env_var}
                  onChange={e =>
                    setForm(prev => ({
                      ...prev,
                      expose_as_env_var: e.target.checked,
                    }))
                  }
                />
              }
              label={
                <Typography variant="body2">
                  Expose mount path as env var
                  {derivedEnvVar && (
                    <span className="kale-envvar-preview">
                      {' '}
                      → {derivedEnvVar}
                    </span>
                  )}
                </Typography>
              }
            />
            {envVarDuplicate && derivedEnvVar && (
              <Typography variant="caption" className="kale-volume-warning">
                Env var "{derivedEnvVar}" already used by another volume
              </Typography>
            )}
          </div>
        </DialogContent>

        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCommit}
            disabled={!canSubmit}
          >
            {editingIdx !== null ? 'Save' : 'Add volume'}
          </Button>
        </DialogActions>
      </Dialog>

      <NotebookVolumesDialog
        open={showNotebookDialog}
        notebook={notebook}
        kernel={kernel}
        onClose={() => setShowNotebookDialog(false)}
        onAdd={handleNotebookAdd}
      />
    </>
  );
};
