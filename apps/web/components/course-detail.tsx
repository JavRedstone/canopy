"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Alert from "@mui/material/Alert";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogActions from "@mui/material/DialogActions";
import Button from "@mui/material/Button";
import { CoursePlanningNotStartedError, CourseMapResponse, CoursePointsResponse, CourseProgressResponse, CourseSummary, deleteCourse, exportCoursebook, getCourse, getCourseMap, getCoursePoints, getCourseProgress, regenerateCourse, resumeCourseLessons } from "@/lib/api";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { CourseCategoryBadge } from "@/components/course-category-badge";
import { CourseProgressSteps } from "@/components/course-progress";
import { MasteryDashboard } from "@/components/mastery-dashboard";
import { RecommendationsPanel } from "@/components/recommendations-panel";
import { CourseSettingsDialog } from "@/components/course-settings-dialog";
import { CourseSourcesDialog } from "@/components/course-sources-dialog";
import { Icon } from "@/components/icon";
import { SettingsMenu, SettingsMenuAction } from "@/components/settings-menu";
import { conceptKindIcon } from "@/lib/concept-kind";
import { createClient } from "@/lib/supabase/client";

const pollIntervalMs = 5000;
const fullRefreshEveryPolls = 3;

export function CourseDetail({ courseId }: { courseId: string }) {
  const router = useRouter();
  const [course, setCourse] = useState<CourseSummary>();
  const [progress, setProgress] = useState<CourseProgressResponse>();
  const [map, setMap] = useState<CourseMapResponse>();
  const [points, setPoints] = useState<CoursePointsResponse>();
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string>();
  const [refreshError, setRefreshError] = useState<string>();
  const [regenerating, setRegenerating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string>();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [detailTab, setDetailTab] = useState<"content" | "mastery">("content");
  const fullLoadRef = useRef<() => Promise<void>>(async () => {});
  const progressRefreshRef = useRef<() => Promise<void>>(async () => {});
  const pollCountRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    async function loadFull() {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) return;
      try {
        const token = data.session.access_token;
        const [courseSummary, courseProgress, coursePoints] = await Promise.all([
          getCourse(courseId, token),
          getCourseProgress(courseId, token),
          getCoursePoints(courseId, token)
        ]);
        if (cancelled) return;
        // Right after creating or regenerating a course, the active version has no concept
        // skeleton yet -- getCourseMap 409s until planning produces one. That's not a fatal
        // error, just "not ready yet": fall back to an empty map so the build-progress
        // stepper renders instead of a hard error screen, and let the poll below refetch
        // once planning has actually produced a skeleton.
        let courseMap: CourseMapResponse;
        try {
          courseMap = await getCourseMap(courseId, token);
        } catch (mapError) {
          if (!(mapError instanceof CoursePlanningNotStartedError)) throw mapError;
          courseMap = { course_id: courseId, version: 0, modules: [] };
        }
        if (cancelled) return;
        setCourse(courseSummary);
        setProgress(courseProgress);
        setMap(courseMap);
        setPoints(coursePoints);
        setRefreshError(undefined);
        setState("ready");
      } catch (caught) {
        if (!cancelled) {
          setErrorMessage(caught instanceof Error ? caught.message : "Unknown error.");
          setState("error");
        }
      }
    }

    async function refreshProgress() {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) return;
      try {
        const nextProgress = await getCourseProgress(courseId, data.session.access_token);
        if (cancelled) return;
        setProgress(nextProgress);
        setRefreshError(undefined);
        pollCountRef.current += 1;
        if (
          pollCountRef.current % fullRefreshEveryPolls === 0 ||
          nextProgress.stage === "ready" ||
          nextProgress.stage === "failed"
        ) {
          await loadFull();
        }
      } catch (caught) {
        if (!cancelled) {
          setRefreshError(caught instanceof Error ? caught.message : "Unable to refresh course progress.");
        }
      }
    }

    fullLoadRef.current = loadFull;
    progressRefreshRef.current = refreshProgress;
    void loadFull();
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  useEffect(() => {
    if (!progress || progress.stage === "ready" || progress.stage === "failed") return;
    const timer = setTimeout(() => void progressRefreshRef.current(), pollIntervalMs);
    return () => clearTimeout(timer);
  }, [progress]);

  async function handleRegenerate() {
    setRegenerating(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      await regenerateCourse(courseId, data.session.access_token);
      setMap(undefined);
      setState("loading");
      await fullLoadRef.current();
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Unable to regenerate the course.");
      setState("error");
    } finally {
      setRegenerating(false);
    }
  }

  async function handleResumeRemainingLessons() {
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      await resumeCourseLessons(courseId, data.session.access_token);
      await progressRefreshRef.current();
    } catch (caught) {
      setRefreshError(caught instanceof Error ? caught.message : "Unable to resume remaining lessons.");
    }
  }

  async function handleExportTextbook() {
    try {
      setExporting(true);
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const pdf = await exportCoursebook(courseId, data.session.access_token);
      const url = URL.createObjectURL(pdf);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${course?.title.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "course"}-coursebook.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setRefreshError(caught instanceof Error ? caught.message : "Unable to export the coursebook.");
    } finally {
      setExporting(false);
    }
  }

  async function handleDelete() {
    if (!course) return;
    setConfirmDeleteOpen(false);
    setDeleting(true);
    setDeleteError(undefined);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      await deleteCourse(courseId, data.session.access_token);
      router.push("/courses");
    } catch (caught) {
      setDeleteError(caught instanceof Error ? caught.message : "Unable to delete the course.");
      setDeleting(false);
    }
  }

  if (state === "loading") {
    return (
      <Stack direction="row" sx={{ alignItems: "center", gap: 1.5, color: "text.secondary" }}>
        <CircularProgress size={18} /> <Typography>Loading course…</Typography>
      </Stack>
    );
  }
  if (state === "error") return <Alert severity="error">{errorMessage ?? "We could not load this course."}</Alert>;
  if (!course || !progress || !map) return null;

  const coursebookConcepts = map.modules.flatMap((module) => module.concepts);
  const settingsActions: SettingsMenuAction[] = [
    { label: "Modify", icon: "edit", onClick: () => setSettingsOpen(true), disabled: regenerating || deleting },
    { label: regenerating ? "Regenerating…" : "Regenerate", icon: "refresh", onClick: handleRegenerate, disabled: regenerating || deleting },
    { label: deleting ? "Deleting…" : "Delete", icon: "delete", onClick: () => setConfirmDeleteOpen(true), disabled: regenerating || deleting, danger: true },
  ];

  return (
    <Box>
      <Breadcrumbs items={[{ label: "My courses", href: "/courses" }, { label: course.title }]} />
      <Stack direction="row" sx={{ alignItems: "flex-start", justifyContent: "space-between", gap: 3, mb: 4 }}>
        <Stack direction="row" sx={{ alignItems: "center", gap: 1.75, minWidth: 0 }}>
          <CourseCategoryBadge title={course.title} goal={course.goal} />
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="overline" color="text.secondary">{course.status}</Typography>
            <Typography variant="h4" sx={{ letterSpacing: "-0.02em", my: 0.25 }}>{course.title}</Typography>
            <Typography color="text.secondary">{course.goal}</Typography>
          </Box>
        </Stack>
        <Stack direction="row" sx={{ alignItems: "center", gap: 1, flexShrink: 0 }}>
          {points && points.points_total > 0 ? (
            <Chip
              icon={<Icon name="star" />}
              label={`${points.points_earned} / ${points.points_total} pts`}
              title={`${points.points_per_lesson} points per lesson`}
              variant="outlined"
              sx={{ "& .MuiChip-icon": { color: "#f5c518" } }}
            />
          ) : null}
          <Button size="small" variant="outlined" startIcon={<Icon name="folder_open" />} onClick={() => setSourcesOpen(true)}>Sources</Button>
          <SettingsMenu actions={settingsActions} label="Course settings" />
        </Stack>
      </Stack>

      <CourseSettingsDialog course={course} open={settingsOpen} onOpenChange={setSettingsOpen} onSaved={setCourse} />
      <CourseSourcesDialog courseId={courseId} open={sourcesOpen} onOpenChange={setSourcesOpen} />

      <Dialog open={confirmDeleteOpen} onClose={() => setConfirmDeleteOpen(false)}>
        <DialogTitle>Delete course?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Delete &quot;{course.title}&quot;? This removes the course and all of its lessons and progress. This cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button variant="text" onClick={() => setConfirmDeleteOpen(false)}>Cancel</Button>
          <Button variant="contained" color="error" onClick={handleDelete}>Delete</Button>
        </DialogActions>
      </Dialog>

      {progress.stage !== "ready" ? <CourseProgressSteps progress={progress} onResume={handleResumeRemainingLessons} /> : null}
      {refreshError ? <Alert severity="error" sx={{ mb: 2 }}>{refreshError} Retrying automatically…</Alert> : null}
      {deleteError ? <Alert severity="error" sx={{ mb: 2 }}>{deleteError}</Alert> : null}

      {progress.stage === "ready" ? <RecommendationsPanel courseId={courseId} /> : null}

      {progress.stage === "ready" && coursebookConcepts.length > 0 ? (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
          <Box
            sx={{
              position: "relative", overflow: "hidden", mb: 3, p: { xs: 2.25, sm: 3 }, borderRadius: 3,
              color: "white", background: "linear-gradient(120deg, #312e81 0%, #4338ca 52%, #0f766e 130%)",
              boxShadow: "0 18px 40px rgba(49, 46, 129, 0.22)"
            }}
          >
            <Box sx={{ position: "absolute", width: 260, height: 260, borderRadius: "50%", bgcolor: "rgba(255,255,255,0.08)", top: -130, right: -70 }} />
            <Stack direction={{ xs: "column", sm: "row" }} sx={{ position: "relative", alignItems: { sm: "center" }, justifyContent: "space-between", gap: 3 }}>
              <Stack sx={{ gap: 1.1, maxWidth: 610 }}>
                <Stack direction="row" sx={{ alignItems: "center", gap: 0.75 }}>
                  <Icon name="auto_stories" />
                  <Typography variant="overline" sx={{ letterSpacing: "0.13em", fontWeight: 700, color: "#c7d2fe" }}>Your coursebook</Typography>
                </Stack>
                <Typography variant="h4" sx={{ fontWeight: 750, letterSpacing: "-0.025em" }}>{course.title}</Typography>
                <Typography sx={{ color: "#e0e7ff", lineHeight: 1.55 }}>
                  A polished reading edition with {map.modules.length} modules and {coursebookConcepts.length} learning sections, including linked references.
                </Typography>
                <Stack direction="row" sx={{ flexWrap: "wrap", gap: 0.75, mt: 0.5 }}>
                  {map.modules.slice(0, 3).map((module) => <Chip key={module.position} size="small" label={module.title} sx={{ bgcolor: "rgba(255,255,255,0.13)", color: "white", border: "1px solid rgba(255,255,255,0.18)" }} />)}
                  {map.modules.length > 3 ? <Chip size="small" label={`+${map.modules.length - 3} more`} sx={{ bgcolor: "rgba(255,255,255,0.13)", color: "white" }} /> : null}
                </Stack>
                <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap", mt: 1 }}>
                  <Button variant="contained" color="inherit" startIcon={exporting ? <CircularProgress size={16} /> : <Icon name="download" />} onClick={() => void handleExportTextbook()} disabled={exporting} sx={{ color: "#312e81", bgcolor: "white", fontWeight: 700, "&:hover": { bgcolor: "#eef2ff" } }}>
                    {exporting ? "Preparing PDF…" : "Download coursebook"}
                  </Button>
                  <Button variant="text" startIcon={<Icon name="folder_open" />} onClick={() => setSourcesOpen(true)} sx={{ color: "#e0e7ff" }}>Browse sources</Button>
                </Stack>
              </Stack>
              <Box sx={{ alignSelf: { xs: "flex-start", sm: "center" }, width: 135, minHeight: 174, p: 1.5, borderRadius: 1.5, bgcolor: "#f8fafc", color: "#172554", boxShadow: "0 14px 25px rgba(15, 23, 42, 0.27)", transform: { sm: "rotate(3deg)" } }}>
                <Icon name="menu_book" />
                <Typography sx={{ mt: 3, fontWeight: 800, lineHeight: 1.18, fontSize: "0.95rem" }}>{course.title}</Typography>
                <Box sx={{ height: 3, width: 38, bgcolor: "#2dd4bf", mt: 1.2, mb: 1 }} />
                <Typography variant="caption" color="text.secondary">Canopy Coursebook</Typography>
              </Box>
            </Stack>
          </Box>
        </motion.div>
      ) : null}

      {progress.stage === "ready" && map.modules.length > 0 ? (
        <Tabs
          value={detailTab}
          onChange={(_event, value) => setDetailTab(value)}
          sx={{ minHeight: 36, mb: 2, borderBottom: 1, borderColor: "divider" }}
        >
          <Tab value="content" icon={<Icon name="menu_book" />} iconPosition="start" label="Content" sx={{ minHeight: 36, py: 1, textTransform: "none" }} />
          <Tab value="mastery" icon={<Icon name="insights" />} iconPosition="start" label="Mastery" sx={{ minHeight: 36, py: 1, textTransform: "none" }} />
        </Tabs>
      ) : null}

      {detailTab === "mastery" && progress.stage === "ready" && map.modules.length > 0 ? (
        <MasteryDashboard courseId={courseId} />
      ) : map.modules.length === 0 ? (
        progress.stage === "ready" ? <Typography color="text.secondary">This course has no modules yet.</Typography> : null
      ) : (
        <Stack sx={{ gap: 1.25 }}>
          {map.modules.map((module, index) => (
            <motion.div
              key={module.position}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: Math.min(index * 0.04, 0.3) }}
            >
              <Accordion disableGutters>
                <AccordionSummary expandIcon={<Icon name="expand_more" />}>
                  <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", width: "100%", pr: 1 }}>
                    <Typography sx={{ fontWeight: 700 }}>
                      {module.position}. {module.title}
                    </Typography>
                    {module.concepts.length === 0 ? (
                      <Stack direction="row" sx={{ alignItems: "center", gap: 0.75, color: "text.secondary", fontSize: "0.85rem" }}>
                        <CircularProgress size={14} /> Generating…
                      </Stack>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        {module.concepts.length} concept{module.concepts.length === 1 ? "" : "s"}
                      </Typography>
                    )}
                  </Stack>
                </AccordionSummary>
                <AccordionDetails>
                  {module.concepts.length === 0 ? (
                    <Stack direction="row" sx={{ alignItems: "center", gap: 1, color: "text.secondary" }}>
                      <CircularProgress size={16} /> <Typography>Generating concepts…</Typography>
                    </Stack>
                  ) : (
                    <List disablePadding sx={{ display: "grid", gap: 1 }}>
                      {module.concepts.map((concept) => {
                        const building = progress.current_lesson_title === concept.title;
                        return (
                          <ListItemButton
                            key={concept.slug}
                            component={Link}
                            href={`/courses/${courseId}/concepts/${concept.slug}`}
                            sx={{ border: 1, borderColor: "divider", borderRadius: 1.5 }}
                          >
                            <ListItemIcon sx={{ minWidth: 44 }}>
                              <Icon name={conceptKindIcon(concept.kind)} />
                            </ListItemIcon>
                            <ListItemText primary={concept.title} secondary={concept.summary_markdown} />
                            {building ? (
                              <Chip size="small" icon={<CircularProgress size={12} sx={{ color: "inherit" }} />} label="Building…" />
                            ) : (
                              <Chip
                                size="small"
                                icon={concept.completed ? <Icon name="check" /> : undefined}
                                label={concept.kind}
                                color="success"
                                variant={concept.completed ? "filled" : "outlined"}
                                sx={{ textTransform: "capitalize" }}
                              />
                            )}
                          </ListItemButton>
                        );
                      })}
                    </List>
                  )}
                </AccordionDetails>
              </Accordion>
            </motion.div>
          ))}
        </Stack>
      )}
    </Box>
  );
}
