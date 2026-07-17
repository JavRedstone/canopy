"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { Icon } from "@/components/icon";

const storageKey = "canopy-sidebar-collapsed";

const SetFullBleedContext = createContext<(fullBleed: boolean) => void>(() => {});

/** Hides the persistent sidebar and lets the page fill the entire viewport while
 *  `fullBleed` is true (e.g. a coding lab's editor/console workspace) -- reverts
 *  automatically on unmount or once `fullBleed` goes back to false. */
export function useFullBleed(fullBleed: boolean) {
  const setFullBleed = useContext(SetFullBleedContext);
  useEffect(() => {
    setFullBleed(fullBleed);
    return () => setFullBleed(false);
  }, [fullBleed, setFullBleed]);
}

export function AppShell({ sidebar, children }: { sidebar: React.ReactNode; children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [fullBleed, setFullBleed] = useState(false);

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

  const shellClassName = ["app-shell", collapsed && "sidebar-collapsed", fullBleed && "full-bleed"]
    .filter(Boolean)
    .join(" ");

  return (
    <SetFullBleedContext.Provider value={setFullBleed}>
      <div className={shellClassName}>
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
    </SetFullBleedContext.Provider>
  );
}
