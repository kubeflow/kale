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
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import {
  Autocomplete,
  Box,
  Button,
  createFilterOptions,
  TextField,
  Typography,
} from '@mui/material';

interface IRuntimeImageOption {
  name: string;
  image: string;
}

const filterRuntimeImages = createFilterOptions<IRuntimeImageOption>({
  stringify: option => `${option.name} ${option.image}`,
});

interface IBaseImageSectionProps {
  baseImage?: string;
  resolvedDefaultBaseImage: string;
  runtimeImages: Record<string, string>;
  onUpdateBaseImage: (value: string) => void;
}

export const BaseImageSection: React.FC<IBaseImageSectionProps> = ({
  baseImage,
  resolvedDefaultBaseImage,
  runtimeImages,
  onUpdateBaseImage,
}) => {
  const options = React.useMemo(
    () =>
      Object.entries(runtimeImages).map(([name, image]) => ({ name, image })),
    [runtimeImages],
  );
  const selectedOption = options.find(option => option.image === baseImage);
  const [inputValue, setInputValue] = React.useState(
    selectedOption?.name ?? baseImage ?? '',
  );
  const [selectedImage, setSelectedImage] = React.useState(baseImage ?? '');
  const [copied, setCopied] = React.useState(false);

  React.useEffect(() => {
    setInputValue(selectedOption?.name ?? baseImage ?? '');
    setSelectedImage(baseImage ?? '');
    setCopied(false);
  }, [baseImage, selectedOption?.name]);

  return (
    <>
      <p style={{ margin: '8px 0' }}>
        Default: <strong>{resolvedDefaultBaseImage}</strong>
      </p>

      <Autocomplete<IRuntimeImageOption, false, false, true>
        freeSolo
        clearOnBlur
        fullWidth
        options={options}
        filterOptions={filterRuntimeImages}
        getOptionLabel={option =>
          typeof option === 'string' ? option : option.name
        }
        value={selectedOption ?? baseImage ?? null}
        inputValue={inputValue}
        onInputChange={(_, value, reason) => {
          if (reason === 'input' || reason === 'clear') {
            setInputValue(value);
          }
        }}
        onChange={(_, value) => {
          const image =
            typeof value === 'string' ? value : (value?.image ?? '');
          setInputValue(
            typeof value === 'string' ? value : (value?.name ?? ''),
          );
          setSelectedImage(image);
          setCopied(false);
          onUpdateBaseImage(image);
        }}
        renderOption={(props, option) => (
          <li {...props} key={option.name}>
            <span>
              {option.name}
              <Typography variant="body2" color="text.secondary">
                {option.image}
              </Typography>
            </span>
          </li>
        )}
        renderInput={params => (
          <TextField
            {...params}
            label="Base Image"
            placeholder={resolvedDefaultBaseImage}
            variant="outlined"
          />
        )}
      />

      {selectedImage && (
        <Box sx={{ mt: 1.5 }}>
          <Typography variant="caption" color="text.secondary">
            Image reference
          </Typography>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 1,
              p: 1,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              bgcolor: 'action.hover',
            }}
          >
            <Box
              component="code"
              role="region"
              aria-label="Selected image reference"
              tabIndex={0}
              sx={{
                flex: 1,
                minWidth: 0,
                maxHeight: '2.8em',
                overflowY: 'auto',
                overflowWrap: 'anywhere',
                fontSize: '0.8125rem',
                lineHeight: 1.4,
                userSelect: 'text',
                '&:focus-visible': {
                  outline: '2px solid',
                  outlineColor: 'primary.main',
                  outlineOffset: 2,
                },
              }}
            >
              {selectedImage}
            </Box>
            <Button
              size="small"
              startIcon={<ContentCopyIcon fontSize="small" />}
              onClick={async () => {
                setCopied(false);
                try {
                  if (navigator.clipboard) {
                    await navigator.clipboard.writeText(selectedImage);
                    setCopied(true);
                  }
                } catch {
                  setCopied(false);
                }
              }}
              sx={{ flexShrink: 0 }}
            >
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </Box>
        </Box>
      )}

      <Button
        onClick={() => {
          setInputValue('');
          setSelectedImage('');
          setCopied(false);
          onUpdateBaseImage('');
        }}
        color="secondary"
        style={{ marginTop: '8px' }}
      >
        Reset to Default
      </Button>
    </>
  );
};
