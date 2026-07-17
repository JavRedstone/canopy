"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { motion } from "motion/react";
import Box from "@mui/material/Box";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import { Icon } from "@/components/icon";

const storageKey = "canopy-sidebar-collapsed";
const drawerWidth = 220;

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

  const showSidebar = !fullBleed;
  const sidebarWidth = collapsed ? 0 : drawerWidth;

  return (
    <SetFullBleedContext.Provider value={setFullBleed}>
      <Box sx={{ display: "flex", minHeight: "100vh", height: fullBleed ? "100vh" : undefined, overflow: fullBleed ? "hidden" : undefined }}>
        {showSidebar ? (
          <>
            <Drawer
              variant="permanent"
              sx={{
                width: sidebarWidth,
                flexShrink: 0,
                transition: (theme) => theme.transitions.create("width", { duration: 160 }),
                "& .MuiDrawer-paper": {
                  width: sidebarWidth,
                  boxSizing: "border-box",
                  overflowX: "hidden",
                  border: 0,
                  borderRight: collapsed ? 0 : 1,
                  borderColor: "divider",
                  transition: (theme) => theme.transitions.create("width", { duration: 160 })
                }
              }}
            >
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 2.25,
                  height: "100%",
                  p: 2.25,
                  whiteSpace: "nowrap",
                  opacity: collapsed ? 0 : 1,
                  pointerEvents: collapsed ? "none" : "auto",
                  transition: (theme) => theme.transitions.create("opacity", { duration: 120 })
                }}
              >
                {sidebar}
              </Box>
            </Drawer>
            <motion.div
              animate={{ left: collapsed ? 12 : sidebarWidth - 12 }}
              transition={{ type: "spring", stiffness: 400, damping: 32 }}
              style={{ position: "fixed", top: 24, zIndex: 1 }}
            >
              <IconButton
                size="small"
                onClick={() => setCollapsed((current) => !current)}
                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                sx={{ bgcolor: "background.paper", border: 1, borderColor: "divider", "&:hover": { borderColor: "text.primary" } }}
              >
                <Icon name={collapsed ? "chevron_right" : "chevron_left"} />
              </IconButton>
            </motion.div>
          </>
        ) : null}

        <Box
          component="main"
          sx={{
            flex: 1,
            minWidth: 0,
            overflowX: "hidden",
            pt: showSidebar && collapsed ? 5 : undefined,
            display: fullBleed ? "flex" : undefined,
            flexDirection: fullBleed ? "column" : undefined,
            height: fullBleed ? "100vh" : undefined,
            overflow: fullBleed ? "hidden" : undefined
          }}
        >
          {children}
        </Box>
      </Box>
    </SetFullBleedContext.Provider>
  );
}
