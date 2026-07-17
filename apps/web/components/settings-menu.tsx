"use client";

import { Menu } from "@base-ui/react/menu";
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
  return (
    <Menu.Root>
      <Menu.Trigger className="settings-menu-trigger" aria-label={label}>
        <Icon name="settings" />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner className="settings-menu-positioner" side="bottom" align="end" sideOffset={6}>
          <Menu.Popup className="settings-menu-popup">
            {actions.map((action) => (
              <Menu.Item
                className={`settings-menu-item${action.danger ? " settings-menu-item-danger" : ""}`}
                disabled={action.disabled}
                onClick={action.onClick}
                key={action.label}
              >
                <Icon name={action.icon} />
                {action.label}
              </Menu.Item>
            ))}
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}
