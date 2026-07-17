"use client";

import { useState, MouseEvent } from "react";
import IconButton from "@mui/material/IconButton";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import { Icon } from "@/components/icon";

export interface SettingsMenuAction {
  label: string;
  icon: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}

/** A gear-icon dropdown for the actions every course/lesson page needs (modify,
 *  regenerate, delete, ...) so those don't sprawl into a different button layout on
 *  every page that has them. */
export function SettingsMenu({ actions, label = "Settings" }: { actions: SettingsMenuAction[]; label?: string }) {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const open = Boolean(anchorEl);

  function handleOpen(event: MouseEvent<HTMLElement>) {
    setAnchorEl(event.currentTarget);
  }

  function handleClose() {
    setAnchorEl(null);
  }

  return (
    <>
      <IconButton aria-label={label} onClick={handleOpen} size="medium">
        <Icon name="settings" />
      </IconButton>
      <Menu anchorEl={anchorEl} open={open} onClose={handleClose} anchorOrigin={{ vertical: "bottom", horizontal: "right" }} transformOrigin={{ vertical: "top", horizontal: "right" }}>
        {actions.map((action) => (
          <MenuItem
            key={action.label}
            disabled={action.disabled}
            onClick={() => {
              handleClose();
              action.onClick();
            }}
            sx={action.danger ? { color: "error.main" } : undefined}
          >
            <ListItemIcon sx={action.danger ? { color: "error.main" } : undefined}>
              <Icon name={action.icon} />
            </ListItemIcon>
            <ListItemText>{action.label}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
