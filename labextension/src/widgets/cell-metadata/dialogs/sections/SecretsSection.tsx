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
import { Button, Grid } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import { Input } from '../../../../components/Input';
import { ISecretRef } from '../../../../lib/TagsUtils';

// Core patterns, defined once and shared between the live per-field `regex`
// (which additionally allows an empty string, since a row isn't done until
// every field is filled in) and the strict `isRowComplete` check used to
// gate what gets committed and whether another row can be added. Keeps this
// in sync with K8sSecretNameValidator / K8sSecretKeyValidator /
// EnvVarNameValidator in kale/config/validators.py.
const SECRET_NAME_PATTERN =
  '[a-z0-9]([-a-z0-9]*[a-z0-9])?(\\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*';
const SECRET_KEY_PATTERN = '[-._a-zA-Z0-9]+';
const ENV_NAME_PATTERN = '[a-zA-Z_][a-zA-Z0-9_]*';

const SECRET_NAME_REGEX = new RegExp(`^${SECRET_NAME_PATTERN}$`);
const SECRET_KEY_REGEX = new RegExp(`^${SECRET_KEY_PATTERN}$`);
const ENV_NAME_REGEX = new RegExp(`^${ENV_NAME_PATTERN}$`);

// A single secret mapping, as edited in this section. `envName` is kept
// apart from the rest since it's the key of the outer `secrets` map:
// renaming it means replacing the map entry rather than mutating a value.
export interface ISecretRow {
  id: number;
  envName: string;
  secretName: string;
  secretKey: string;
}

const isRowComplete = (row: ISecretRow): boolean =>
  SECRET_NAME_REGEX.test(row.secretName) &&
  SECRET_KEY_REGEX.test(row.secretKey) &&
  ENV_NAME_REGEX.test(row.envName);

// Stable per-row id for React's `key`, since `envName` can be blank or
// duplicated mid-edit and array index shifts whenever a row is deleted.
let nextRowId = 0;

const secretsToRows = (secrets: {
  [envName: string]: ISecretRef;
}): ISecretRow[] =>
  Object.keys(secrets).map(envName => ({
    id: nextRowId++,
    envName,
    ...secrets[envName],
  }));

// Only rows that pass every field's validation are written to the notebook's
// tags - an incomplete or malformed row (e.g. a blank Secret Key, or a Secret
// Name that doesn't match K8sSecretNameValidator) is silently dropped here
// rather than surfacing as a confusing backend error at compile time.
const rowsToSecrets = (
  rows: ISecretRow[],
): { [envName: string]: ISecretRef } => {
  const secrets: { [envName: string]: ISecretRef } = {};
  rows.forEach(row => {
    if (isRowComplete(row)) {
      secrets[row.envName] = {
        secretName: row.secretName,
        secretKey: row.secretKey,
      };
    }
  });
  return secrets;
};

interface ISecretsSectionProps {
  secrets: { [envName: string]: ISecretRef };
  updateSecrets: (secrets: { [envName: string]: ISecretRef }) => void;
  // Keeps an in-progress (not yet valid) row alive across tab switches: this
  // section unmounts whenever the user leaves the Secrets tab (StepConfigDialog
  // only renders the active tab's content), which would otherwise silently
  // drop anything the user was in the middle of typing. Owned by
  // StepConfigDialog, which outlives this section's mount/unmount cycles and
  // clears it when the whole dialog closes.
  draftRowsRef: React.MutableRefObject<ISecretRow[] | null>;
}

export const SecretsSection: React.FC<ISecretsSectionProps> = ({
  secrets,
  updateSecrets,
  draftRowsRef,
}) => {
  // Local state is the source of truth while this section is mounted: an
  // in-progress row (e.g. envName not filled in yet) is excluded from what
  // gets written to the notebook's tags (see rowsToSecrets), so deriving
  // rows straight from the secrets prop on every render would make that row
  // vanish as soon as the user typed into Secret Name/Key before Env Var
  // Name. The lazy initializer resyncs from the committed tags each time
  // this section (re)mounts, i.e. each time the Secrets tab is (re)selected -
  // unless a draft was left behind by a previous mount, in which case that
  // takes precedence over re-deriving from the (necessarily narrower) tags.
  const [rows, setRows] = React.useState<ISecretRow[]>(
    () => draftRowsRef.current ?? secretsToRows(secrets),
  );

  const commit = (newRows: ISecretRow[]) => {
    setRows(newRows);
    draftRowsRef.current = newRows;
    updateSecrets(rowsToSecrets(newRows));
  };

  const updateRow = (index: number, patch: Partial<ISecretRow>) => {
    commit(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const deleteRow = (index: number) => {
    commit(rows.filter((_, i) => i !== index));
  };

  const addRow = () => {
    commit([
      ...rows,
      { id: nextRowId++, envName: '', secretName: '', secretKey: '' },
    ]);
  };

  // Block piling up more empty/malformed rows before the last one is
  // actually usable.
  const lastRow = rows[rows.length - 1];
  const canAddRow = !lastRow || isRowComplete(lastRow);

  return (
    <>
      <p style={{ margin: '0 0 8px' }}>
        Inject Kubernetes Secret values as environment variables, instead of
        hardcoding credentials in the notebook.
      </p>
      {rows.map((row, index) => (
        <Grid
          container
          key={row.id}
          spacing={1}
          sx={{ alignItems: 'center', marginBottom: '4px' }}
        >
          <Grid size={{ xs: 4 }}>
            <Input
              variant="standard"
              label="Secret Name"
              value={row.secretName}
              regex={`^(${SECRET_NAME_PATTERN})?$`}
              regexErrorMsg="Must be a valid Kubernetes Secret name."
              updateValue={(v: string) => updateRow(index, { secretName: v })}
            />
          </Grid>
          <Grid size={{ xs: 4 }}>
            <Input
              variant="standard"
              label="Secret Key"
              value={row.secretKey}
              regex={`^(${SECRET_KEY_PATTERN})?$`}
              regexErrorMsg="Must be a valid Secret data key."
              updateValue={(v: string) => updateRow(index, { secretKey: v })}
            />
          </Grid>
          <Grid size={{ xs: 3 }}>
            <Input
              variant="standard"
              label="Env Var Name"
              value={row.envName}
              regex={`^(${ENV_NAME_PATTERN})?$`}
              regexErrorMsg="Must be a valid environment variable name."
              updateValue={(v: string) => updateRow(index, { envName: v })}
            />
          </Grid>
          <Grid size={{ xs: 1 }}>
            <Button
              variant="contained"
              size="small"
              title="Remove Secret"
              onClick={() => deleteRow(index)}
              style={{ transform: 'scale(0.9)' }}
            >
              <DeleteIcon />
            </Button>
          </Grid>
        </Grid>
      ))}
      <Button
        variant="outlined"
        size="small"
        startIcon={<AddIcon />}
        onClick={addRow}
        disabled={!canAddRow}
        title={
          canAddRow
            ? undefined
            : 'Finish the current secret (all fields, valid format) before adding another.'
        }
        style={{ marginTop: '8px' }}
      >
        Add Secret
      </Button>
    </>
  );
};
