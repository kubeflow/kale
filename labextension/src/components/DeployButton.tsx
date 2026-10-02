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
import Grid from '@mui/material/Grid';
import Button from '@mui/material/Button';
import ButtonGroup from '@mui/material/ButtonGroup';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import ClickAwayListener from '@mui/material/ClickAwayListener';
import Grow from '@mui/material/Grow';
import Paper from '@mui/material/Paper';
import Popper from '@mui/material/Popper';
import MenuItem from '@mui/material/MenuItem';
import MenuList from '@mui/material/MenuList';
import CircularProgress from '@mui/material/CircularProgress';
import { styled } from '@mui/material/styles';
import type { DeployType } from '../widgets/LeftPanel';

const DeployButtonContainer = styled('div')({
  '& .deploy-button': {
    // Add any specific styling for the deploy button container
  },
});

const StyledButtonGroup = styled(ButtonGroup)({
  width: '100%',
});

const MainButton = styled(Button)({
  width: '100%',
  whiteSpace: 'nowrap',
});

const DropdownButton = styled(Button)({
  width: 'auto',
});

const StyledPopper = styled(Popper)({
  zIndex: 2,
});

interface ISplitDeployButton {
  running: boolean;
  handleClick: (value: DeployType) => void;
  disabled?: boolean;
  // katibRun: boolean;
}

export const SplitDeployButton: React.FunctionComponent<
  ISplitDeployButton
> = props => {
  const [open, setOpen] = React.useState(false);
  const anchorRef = React.useRef<HTMLDivElement>(null);
  const [selectedIndex, setSelectedIndex] = React.useState(0);

  const options: { label: string; value: DeployType }[] = [
    {
      label: 'Compile and Run',
      value: 'run',
    },
    { label: 'Compile and Upload', value: 'upload' },
    { label: 'Compile and Save', value: 'compile' },
  ];

  const handleMenuItemClick = (
    _event: React.MouseEvent<HTMLLIElement>,
    index: number,
  ) => {
    setSelectedIndex(index);
    setOpen(false);
    if (!props.running && !props.disabled) {
      props.handleClick(options[index].value);
    }
  };

  const handleToggle = () => {
    setOpen(prevOpen => !prevOpen);
  };

  const handleClose = (event: Event) => {
    if (
      anchorRef.current &&
      event.target instanceof Node &&
      anchorRef.current.contains(event.target)
    ) {
      return;
    }

    setOpen(false);
  };

  const handleMainButtonClick = () => {
    props.handleClick(options[selectedIndex].value);
  };

  return (
    <DeployButtonContainer>
      <div className="deploy-button">
        <Grid container>
          <Grid size={12} sx={{ padding: '4px 6px' }}>
            <StyledButtonGroup
              variant="contained"
              color="primary"
              ref={anchorRef}
              aria-label="split button"
            >
              <MainButton
                color="primary"
                onClick={handleMainButtonClick}
                disabled={props.running || props.disabled}
              >
                {props.running ? (
                  <CircularProgress thickness={6} size={14} color="secondary" />
                ) : (
                  options[selectedIndex].label
                )}
              </MainButton>
              <DropdownButton
                color="primary"
                size="small"
                aria-controls={open ? 'menu-list-grow' : undefined}
                aria-haspopup="true"
                onClick={handleToggle}
                disabled={props.running || props.disabled}
              >
                <MoreVertIcon />
              </DropdownButton>
            </StyledButtonGroup>
            <StyledPopper
              open={open}
              anchorEl={anchorRef.current}
              transition
              disablePortal
            >
              {({ TransitionProps, placement }) => (
                <Grow
                  {...TransitionProps}
                  style={{
                    transformOrigin:
                      placement === 'bottom' ? 'center top' : 'center bottom',
                  }}
                >
                  <Paper id="menu-list-grow">
                    <ClickAwayListener onClickAway={handleClose}>
                      <MenuList>
                        {options.map((option, index) => (
                          <MenuItem
                            key={option.value}
                            selected={index === selectedIndex}
                            onClick={event => handleMenuItemClick(event, index)}
                          >
                            {option.label}
                          </MenuItem>
                        ))}
                      </MenuList>
                    </ClickAwayListener>
                  </Paper>
                </Grow>
              )}
            </StyledPopper>
          </Grid>
        </Grid>
      </div>
    </DeployButtonContainer>
  );
};
