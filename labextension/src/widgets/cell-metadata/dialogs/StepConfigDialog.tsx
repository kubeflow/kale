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
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Tab,
  Tabs,
} from '@mui/material';
import { ISecretRef } from '../../../lib/TagsUtils';
import { BaseImageSection } from './sections/BaseImageSection';
import { GpuSection, ILimitAction } from './sections/GpuSection';
import { CacheSection } from './sections/CacheSection';
import { ReportSection } from './sections/ReportSection';
import { ISecretRow, SecretsSection } from './sections/SecretsSection';

interface IStepConfigDialogProps {
  open: boolean;
  onClose: () => void;
  stepName: string;
  // Base image
  baseImage?: string;
  resolvedDefaultBaseImage: string;
  onUpdateBaseImage: (value: string) => void;
  runtimeImages: Record<string, string>;
  // GPU / limits
  limits: { [id: string]: string };
  updateLimits: (actions: ILimitAction[]) => void;
  // Caching
  enableCaching?: boolean;
  onUpdateCaching: (value: boolean | undefined) => void;
  // HTML report
  generateHtmlReport?: boolean;
  onUpdateHtmlReport: (value: boolean | undefined) => void;
  // Secrets
  secrets: { [envName: string]: ISecretRef };
  updateSecrets: (secrets: { [envName: string]: ISecretRef }) => void;
}

/**
 * Single "Configure Step" dialog consolidating per-step options (base image,
 * GPU, caching, ...) behind tabs instead of one button/dialog per option.
 * See https://github.com/kubeflow/kale/issues/894 - add new sections here by
 * appending a {label, render} entry to `tabs`, instead of a new standalone
 * dialog/button.
 */
export const StepConfigDialog: React.FC<IStepConfigDialogProps> = props => {
  const [activeTab, setActiveTab] = React.useState(0);

  // Holds an in-progress Secrets row across tab switches (see SecretsSection's
  // draftRowsRef doc). The dialog is modal, so it's never possible to jump to
  // a different step while it's open - closing is the only point where a
  // leftover draft needs to be thrown away.
  const draftSecretRowsRef = React.useRef<ISecretRow[] | null>(null);

  // Always open on the first tab rather than whichever tab was last viewed.
  React.useEffect(() => {
    if (props.open) {
      setActiveTab(0);
    } else {
      draftSecretRowsRef.current = null;
    }
  }, [props.open]);

  const tabs: { label: string; render: () => React.ReactNode }[] = [
    {
      label: 'Base Image',
      render: () => (
        <BaseImageSection
          baseImage={props.baseImage}
          resolvedDefaultBaseImage={props.resolvedDefaultBaseImage}
          runtimeImages={props.runtimeImages}
          onUpdateBaseImage={props.onUpdateBaseImage}
        />
      ),
    },
    {
      label: 'GPU',
      render: () => (
        <GpuSection
          stepName={props.stepName}
          limits={props.limits}
          updateLimits={props.updateLimits}
        />
      ),
    },
    {
      label: 'Caching',
      render: () => (
        <CacheSection
          enableCaching={props.enableCaching}
          onUpdateCaching={props.onUpdateCaching}
        />
      ),
    },
    {
      label: 'Report',
      render: () => (
        <ReportSection
          generateHtmlReport={props.generateHtmlReport}
          onUpdateHtmlReport={props.onUpdateHtmlReport}
        />
      ),
    },
    {
      label: 'Secrets',
      render: () => (
        <SecretsSection
          secrets={props.secrets}
          updateSecrets={props.updateSecrets}
          draftRowsRef={draftSecretRowsRef}
        />
      ),
    },
  ];

  return (
    <Dialog
      open={props.open}
      onClose={props.onClose}
      fullWidth
      maxWidth="md"
      scroll="paper"
      aria-labelledby="step-config-dialog-title"
      aria-describedby="step-config-dialog-description"
    >
      <DialogTitle id="step-config-dialog-title">Configure Step</DialogTitle>
      <Tabs
        value={activeTab}
        onChange={(_, v) => setActiveTab(v)}
        variant="fullWidth"
        sx={{
          '& .MuiTab-root': {
            color: 'var(--jp-ui-font-color2)',
          },
          '& .MuiTab-root.Mui-selected': {
            color: 'var(--jp-ui-font-color1)',
          },
        }}
      >
        {tabs.map(tab => (
          <Tab key={tab.label} label={tab.label} />
        ))}
      </Tabs>
      <DialogContent
        dividers
        id="step-config-dialog-description"
        style={{ minHeight: '220px' }}
      >
        <Box sx={{ paddingTop: '16px' }}>{tabs[activeTab].render()}</Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={props.onClose} color="primary">
          Ok
        </Button>
      </DialogActions>
    </Dialog>
  );
};
