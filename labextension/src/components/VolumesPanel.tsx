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
import { useCallback, useEffect, useRef, useState } from 'react';
import { NotebookPanel } from '@jupyterlab/notebook';
import { Kernel } from '@jupyterlab/services';
import Button from '@mui/material/Button';
import AddIcon from '@mui/icons-material/Add';
import { IVolumeConfig } from '../widgets/LeftPanelTypes';
import { VolumeRow } from './volumes/VolumeRow';
import { AddVolumeDialog } from './volumes/AddVolumeDialog';
import { deriveEnvVarName, IPvcInfo } from './volumes/volumeUtils';
import Commands from '../lib/Commands';

interface IVolumesPanelProps {
  volumes: IVolumeConfig[];
  updateVolumes: (volumes: IVolumeConfig[]) => void;
  notebook: NotebookPanel | null;
  kernel: Kernel.IKernelConnection;
}

export const VolumesPanel: React.FC<IVolumesPanelProps> = ({
  volumes,
  updateVolumes,
  notebook,
  kernel,
}) => {
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [copiedEnvVar, setCopiedEnvVar] = useState<string | null>(null);
  const [pvcAccessModes, setPvcAccessModes] = useState<Map<string, string[]>>(
    new Map(),
  );
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const getCommands = useCallback(
    () => (notebook ? new Commands(notebook, kernel) : null),
    [notebook, kernel],
  );

  // Fetch PVC access modes for display
  useEffect(() => {
    const cmds = getCommands();
    if (!cmds) {
      return;
    }
    cmds
      .listPvcs()
      .then((pvcs: IPvcInfo[]) => {
        const map = new Map<string, string[]>();
        for (const pvc of pvcs) {
          map.set(pvc.name, pvc.access_modes);
        }
        setPvcAccessModes(map);
      })
      .catch(() => {});
  }, [getCommands]);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current);
      }
    };
  }, []);

  const duplicateMountPaths = (() => {
    const seen = new Set<string>();
    const dups = new Set<string>();
    for (const v of volumes) {
      if (seen.has(v.mount_point)) {
        dups.add(v.mount_point);
      }
      seen.add(v.mount_point);
    }
    return dups;
  })();

  const duplicateEnvVars = (() => {
    const seen = new Map<string, string>();
    const dups = new Set<string>();
    for (const v of volumes) {
      if (!v.expose_as_env_var) {
        continue;
      }
      const envName = deriveEnvVarName(v.name);
      if (seen.has(envName)) {
        dups.add(envName);
      } else {
        seen.set(envName, v.name);
      }
    }
    return dups;
  })();

  const openAddDialog = () => {
    setEditingIdx(null);
    setShowAddDialog(true);
  };

  const openEditDialog = (idx: number) => {
    setEditingIdx(idx);
    setShowAddDialog(true);
  };

  const closeDialog = () => {
    setShowAddDialog(false);
    setEditingIdx(null);
  };

  const handleCommit = (entry: IVolumeConfig) => {
    if (editingIdx !== null) {
      updateVolumes(volumes.map((v, i) => (i === editingIdx ? entry : v)));
    } else {
      updateVolumes([...volumes, entry]);
    }
    closeDialog();
  };

  const handleAddMultiple = (entries: IVolumeConfig[]) => {
    const existingNames = new Set(volumes.map(v => v.name));
    const existingMounts = new Set(volumes.map(v => v.mount_point));
    const toAdd = entries.filter(
      e => !existingNames.has(e.name) && !existingMounts.has(e.mount_point),
    );
    if (toAdd.length > 0) {
      updateVolumes([...volumes, ...toAdd]);
    }
    closeDialog();
  };

  const handleCopyEnvVar = (envVarName: string) => {
    navigator.clipboard.writeText(envVarName).catch(() => {});
    setCopiedEnvVar(envVarName);
    if (copyTimeoutRef.current) {
      clearTimeout(copyTimeoutRef.current);
    }
    copyTimeoutRef.current = setTimeout(() => setCopiedEnvVar(null), 2000);
  };

  return (
    <div className="kale-volumes-panel">
      {volumes.length > 0 && (
        <div className="kale-volumes-list">
          {volumes.map((vol, idx) => (
            <VolumeRow
              key={`${vol.name}:${vol.mount_point}`}
              vol={vol}
              accessModes={pvcAccessModes.get(vol.name)}
              isDupMount={duplicateMountPaths.has(vol.mount_point)}
              isDupEnvVar={
                !!vol.expose_as_env_var &&
                duplicateEnvVars.has(deriveEnvVarName(vol.name))
              }
              copiedEnvVar={copiedEnvVar}
              onEdit={() => openEditDialog(idx)}
              onRemove={() =>
                updateVolumes(volumes.filter((_, i) => i !== idx))
              }
              onCopyEnvVar={handleCopyEnvVar}
            />
          ))}
        </div>
      )}

      <Button
        variant="text"
        size="small"
        startIcon={<AddIcon />}
        onClick={openAddDialog}
        className="kale-add-volume-btn"
      >
        Add Volume
      </Button>

      <AddVolumeDialog
        open={showAddDialog}
        editingIdx={editingIdx}
        volumes={volumes}
        notebook={notebook}
        kernel={kernel}
        onClose={closeDialog}
        onCommit={handleCommit}
        onAddMultiple={handleAddMultiple}
      />
    </div>
  );
};
