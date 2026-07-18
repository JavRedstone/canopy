"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Alert from "@mui/material/Alert";
import { CourseSummary, getCourses } from "@/lib/api";
import { CourseCategoryBadge } from "@/components/course-category-badge";
import { Icon } from "@/components/icon";
import { LinkButton } from "@/components/link-button";
import { createClient } from "@/lib/supabase/client";

export function CourseDashboard() {
  const [courses, setCourses] = useState<CourseSummary[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string>();

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function load() {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) return;
      try {
        const nextCourses = await getCourses(data.session.access_token);
        if (cancelled) return;
        setCourses(nextCourses);
        setState("ready");
        if (nextCourses.some((course) => course.status === "draft")) {
          timer = window.setTimeout(() => void load(), 8000);
        }
      } catch (caught) {
        if (!cancelled) {
          setErrorMessage(caught instanceof Error ? caught.message : "Unknown error.");
          setState("error");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  if (state === "loading") {
    return (
      <Stack direction="row" sx={{ alignItems: "center", gap: 1.5, color: "text.secondary" }}>
        <CircularProgress size={18} /> <Typography>Loading your courses…</Typography>
      </Stack>
    );
  }
  if (state === "error") return <Alert severity="error">{errorMessage ?? "We could not load courses."}</Alert>;
  if (courses.length === 0) {
    return (
      <Card variant="outlined" sx={{ maxWidth: 420 }}>
        <CardContent component={Stack} sx={{ gap: 1.5, alignItems: "flex-start" }}>
          <Typography variant="h6">Your first course starts with a source.</Typography>
          <Typography color="text.secondary">Upload a document, choose a goal, and we will create a stable course map.</Typography>
          <LinkButton href="/courses/new" variant="contained">Create a course</LinkButton>
        </CardContent>
      </Card>
    );
  }
  return (
    <List disablePadding sx={{ display: "grid", gap: 1 }}>
      {courses.map((course, index) => (
        <motion.div
          key={course.id}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: Math.min(index * 0.04, 0.3) }}
        >
          <ListItemButton component={Link} href={`/courses/${course.id}`} sx={{ border: 1, borderColor: "divider", borderRadius: 1.5, gap: 1.75 }}>
            <CourseCategoryBadge title={course.title} goal={course.goal} />
            <ListItemText primary={course.title} secondary={course.goal} sx={{ minWidth: 0 }} />
            {course.status === "draft" ? (
              <Chip size="small" icon={<CircularProgress size={12} sx={{ color: "inherit" }} />} label="Building…" />
            ) : course.status === "ready" && course.lessons_total > 0 ? (
              course.lessons_completed === course.lessons_total ? (
                <Chip size="small" icon={<Icon name="check" />} label="Complete" color="success" />
              ) : (
                <Stack direction="row" sx={{ alignItems: "center", gap: 1, flexShrink: 0 }}>
                  <Box sx={{ position: "relative", width: 64, height: 6, borderRadius: 999, bgcolor: "action.hover", overflow: "hidden" }}>
                    <Box
                      sx={{
                        position: "absolute",
                        insetBlock: 0,
                        left: 0,
                        width: `${Math.round((course.lessons_completed / course.lessons_total) * 100)}%`,
                        borderRadius: 999,
                        bgcolor: "primary.main",
                      }}
                    />
                  </Box>
                  <Typography variant="caption" color="text.secondary" sx={{ fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>
                    {course.lessons_completed}/{course.lessons_total}
                  </Typography>
                </Stack>
              )
            ) : (
              <Chip
                size="small"
                label={course.status}
                color="default"
                variant="outlined"
                sx={{ textTransform: "capitalize" }}
              />
            )}
          </ListItemButton>
        </motion.div>
      ))}
    </List>
  );
}
