"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/icon";

const storageKey = "canopy-sidebar-collapsed";

export function AppShell({ sidebar, children }: { sidebar: React.ReactNode; children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    // Server always renders expanded (no access to localStorage); flipping this after
    // mount, rather than reading it in the initializer, avoids a hydration mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCollapsed(localStorage.getItem(storageKey) === "true");
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) localStorage.setItem(storageKey, String(collapsed));
  }, [collapsed, hydrated]);

  return (
    <div className={collapsed ? "app-shell sidebar-collapsed" : "app-shell"}>
      <aside className="sidebar">
        <button
          className="sidebar-toggle"
          onClick={() => setCollapsed((current) => !current)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <Icon name={collapsed ? "chevron_right" : "chevron_left"} />
        </button>
        <div className="sidebar-content">{sidebar}</div>
      </aside>
      <main className="app-main">{children}</main>
    </div>
  );
}
