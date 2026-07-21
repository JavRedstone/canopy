"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { CourseMapResponse, getCourseMap } from "@/lib/api";
import { CanopyLoader } from "@/components/canopy-loader";
import { Icon } from "@/components/icon";
import { conceptKindIcon, conceptKindLabel } from "@/lib/concept-kind";
import { createClient } from "@/lib/supabase/client";

type CourseOutlineValue = {
  map?: CourseMapResponse;
  /** Re-reads the map so per-concept `completed` ticks update after a lesson is finished. */
  refresh: () => Promise<void>;
  collapsed: boolean;
};

const CourseOutlineContext = createContext<CourseOutlineValue>({
  refresh: async () => {},
  collapsed: false,
});

export function useCourseOutline() {
  return useContext(CourseOutlineContext);
}

function CourseOutlineSidebar({ courseId, map, activeSlug, collapsed, onToggle }: { courseId: string; map?: CourseMapResponse; activeSlug: string; collapsed: boolean; onToggle: () => void }) {
  return (
    <Box component="aside" sx={{ display: { xs: "none", md: "block" }, position: "fixed", top: 64, bottom: 0, left: 0, zIndex: 2, width: collapsed ? 56 : 280, overflowX: "hidden", overflowY: "auto", borderRight: 1, borderColor: "divider", bgcolor: "background.paper", p: 1.25, transition: (theme) => theme.transitions.create("width", { duration: 180 }) }}>
      <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", px: collapsed ? 0 : 1, mb: 0.75 }}>
        {!collapsed ? <Typography variant="overline" color="text.secondary">Course outline</Typography> : null}
        <IconButton size="small" onClick={onToggle} aria-label={collapsed ? "Expand course outline" : "Collapse course outline"}>
          <Icon name={collapsed ? "chevron_right" : "chevron_left"} />
        </IconButton>
      </Stack>
      {!collapsed && !map ? <CanopyLoader label="Loading outline…" size={40} py={4} /> : null}
      {!collapsed && map ? <List disablePadding sx={{ display: "grid", gap: 1 }}>
        {map.modules.map((module) => (
          <Box key={module.position}>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", px: 1, pb: 0.5 }}>
              {module.position}. {module.title}
            </Typography>
            {module.concepts.map((item) => (
              <ListItemButton
                key={item.slug}
                component={Link}
                href={`/courses/${courseId}/concepts/${item.slug}`}
                selected={item.slug === activeSlug}
                sx={{ borderRadius: 1, py: 0.75, px: 1, alignItems: "flex-start" }}
              >
                <ListItemIcon sx={{ minWidth: 28, mt: 0.15 }}>
                  <Icon name={conceptKindIcon(item.kind)} />
                </ListItemIcon>
                <ListItemText primary={item.title} secondary={conceptKindLabel(item.kind)} slotProps={{ primary: { sx: { fontSize: "0.82rem", lineHeight: 1.25 } }, secondary: { sx: { fontSize: "0.72rem" } } }} />
                {item.completed ? (
                  <Box component="span" sx={{ mt: 0.15, color: "success.main", display: "inline-flex", "& .material-symbol": { fontSize: 16 } }}>
                    <Icon name="check_circle" />
                  </Box>
                ) : null}
              </ListItemButton>
            ))}
          </Box>
        ))}
      </List> : null}
    </Box>
  );
}

/**
 * Owns the course outline for the whole `/courses/[id]` subtree.
 *
 * This deliberately lives in a layout rather than inside ConceptDetail. Navigating between
 * concepts changes the `[slug]` segment, which remounts the page subtree -- so a sidebar
 * rendered by the page lost its data, its collapsed state and its scroll position on every
 * lesson change, and flashed "Loading outline…" while it refetched. The `[id]` segment does
 * not change across that navigation, so a layout-level owner survives it.
 */
export function CourseOutlineProvider({ courseId, children }: { courseId: string; children: React.ReactNode }) {
  const [map, setMap] = useState<CourseMapResponse>();
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const activeSlug = pathname.split("/concepts/")[1] ?? "";

  /** For consumers to call after a completion event; not used for the initial load, which
   *  needs its own cancellation and must not call setState straight from an effect body. */
  const refresh = useCallback(async () => {
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) return;
      setMap(await getCourseMap(courseId, data.session.access_token));
    } catch {
      // Non-fatal: the outline keeps its last known state.
    }
  }, [courseId]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const { data } = await createClient().auth.getSession();
        if (!data.session || cancelled) return;
        const next = await getCourseMap(courseId, data.session.access_token);
        if (!cancelled) setMap(next);
      } catch {
        // Non-fatal: the outline keeps its last known state.
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  const value = useMemo(() => ({ map, refresh, collapsed }), [map, refresh, collapsed]);

  return (
    <CourseOutlineContext.Provider value={value}>
      {/* The course overview page has no outline rail, only the concept pages do. */}
      {activeSlug ? (
        <CourseOutlineSidebar
          courseId={courseId}
          map={map}
          activeSlug={activeSlug}
          collapsed={collapsed}
          onToggle={() => setCollapsed((current) => !current)}
        />
      ) : null}
      {children}
    </CourseOutlineContext.Provider>
  );
}
