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
import { alpha, darken } from "@mui/material/styles";
import { CoursePlanningNotStartedError, CourseMapResponse, CoursePointsResponse, CourseProgressResponse, CourseSummary, DemoAutoCompleteOptions, DemoJobStatus, cancelDemoAutoComplete, clearDemoProgress, deleteCourse, exportCoursebook, getCourse, getCourseMap, getCoursePoints, getCourseProgress, getDemoAutoCompleteStatus, regenerateCourse, resumeCourseLessons, startDemoAutoComplete } from "@/lib/api";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { CertificateDialog } from "@/components/certificate-dialog";
import { CourseCategoryBadge } from "@/components/course-category-badge";
import { CourseProgressSteps } from "@/components/course-progress";
import { MasteryDashboard } from "@/components/mastery-dashboard";
import { PracticeDrill } from "@/components/practice-drill";
import { RecommendationsPanel } from "@/components/recommendations-panel";
import { CourseSettingsDialog } from "@/components/course-settings-dialog";
import { CourseShareDialog } from "@/components/course-share-dialog";
import { CourseSourcesDialog } from "@/components/course-sources-dialog";
import { DemoAutoCompleteDialog } from "@/components/demo-autocomplete-dialog";
import { Icon } from "@/components/icon";
import { SettingsMenu, SettingsMenuAction } from "@/components/settings-menu";
import { conceptKindIcon } from "@/lib/concept-kind";
import { getCourseCategory } from "@/lib/course-category";
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
  const [shareOpen, setShareOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);
  const [demoJob, setDemoJob] = useState<DemoJobStatus>();
  const [clearingDemo, setClearingDemo] = useState(false);
  const [confirmClearDemoOpen, setConfirmClearDemoOpen] = useState(false);
  const [certificateOpen, setCertificateOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [detailTab, setDetailTab] = useState<"content" | "practice" | "mastery">("content");
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

  // Deliberately independent of demoOpen: a run keeps going (and stays trackable) whether
  // or not its dialog is open, so closing it never leaves you guessing whether it stopped.
  useEffect(() => {
    if (!demoJob || demoJob.state !== "running") return;
    const timer = window.setTimeout(async () => {
      try {
        const { data } = await createClient().auth.getSession();
        if (!data.session) return;
        setDemoJob(await getDemoAutoCompleteStatus(courseId, demoJob.job_id, data.session.access_token));
      } catch {
        // Non-fatal: keep the last known status and try again on the next tick.
      }
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [courseId, demoJob]);

  // Mirrors what a real learner's own actions already trigger elsewhere (a mastery/course-map
  // refresh after answering a quiz or submitting a lab) -- as the demo finishes each concept,
  // pull the course's own checkmarks/points/mastery back in so the page visibly updates while
  // it runs, not just the dialog's own results list.
  useEffect(() => {
    if (!demoJob) return;
    void fullLoadRef.current();
    // Deliberately narrower than the full demoJob object: only re-run when a concept
    // actually finishes or the run reaches a terminal state, not on every 1.5s poll tick
    // (current_concept_title changes far more often and isn't worth a reload on its own).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoJob?.completed, demoJob?.state]);

  // Pop the certificate up the first time a visit finds every lesson done -- sessionStorage
  // (not a ref) so it fires again on a fresh visit later, but not on every re-render or
  // background poll within the same tab session while the learner keeps browsing the course.
  useEffect(() => {
    if (!course || course.lessons_total === 0 || course.lessons_completed < course.lessons_total) return;
    const seenKey = `canopy:certificate-shown:${courseId}`;
    if (window.sessionStorage.getItem(seenKey)) return;
    window.sessionStorage.setItem(seenKey, "1");
    // Popup eligibility depends on sessionStorage, an external store React doesn't track --
    // there's no render-time way to derive it, so the setState has to live here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCertificateOpen(true);
  }, [course, courseId]);

  async function handleStartDemo(options: DemoAutoCompleteOptions) {
    const { data } = await createClient().auth.getSession();
    if (!data.session) throw new Error("Your session has expired. Please sign in again.");
    setDemoJob(await startDemoAutoComplete(courseId, options, data.session.access_token));
  }

  async function handleCancelDemo() {
    if (!demoJob) return;
    const { data } = await createClient().auth.getSession();
    if (!data.session) throw new Error("Your session has expired. Please sign in again.");
    await cancelDemoAutoComplete(courseId, demoJob.job_id, data.session.access_token);
  }

  async function handleClearDemo() {
    setConfirmClearDemoOpen(false);
    setClearingDemo(true);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      await clearDemoProgress(courseId, undefined, data.session.access_token);
      await fullLoadRef.current();
    } catch (caught) {
      setRefreshError(caught instanceof Error ? caught.message : "Unable to clear demo progress.");
    } finally {
      setClearingDemo(false);
    }
  }

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
  const courseCategory = getCourseCategory(course.title, course.goal);
  const coursebookGradients: Record<string, string> = {
    security: "linear-gradient(120deg, #581c27 0%, #9f1239 58%, #be123c 130%)",
    ml: "linear-gradient(120deg, #312e81 0%, #6d28d9 58%, #7c3aed 130%)",
    data: "linear-gradient(120deg, #78350f 0%, #b45309 58%, #d97706 130%)",
    web: "linear-gradient(120deg, #0c4a6e 0%, #0369a1 58%, #0284c7 130%)",
    backend: "linear-gradient(120deg, #14532d 0%, #15803d 58%, #16a34a 130%)",
    cloud: "linear-gradient(120deg, #134e4a 0%, #0f766e 58%, #0d9488 130%)",
    code: "linear-gradient(120deg, #365314 0%, #4d7c0f 58%, #65a30d 130%)",
    default: "linear-gradient(120deg, #334155 0%, #475569 58%, #64748b 130%)"
  };
  const coursebookGradient = coursebookGradients[courseCategory.key] ?? coursebookGradients.default;
  // The button sitting on the white card needs a solid, readable color, not a gradient --
  // this is each gradient's own darkest stop, so it always matches the card instead of a
  // fixed color chosen for one category (previously hardcoded to the "ml" gradient's
  // indigo, which looked like an arbitrary unrelated blue on every other category).
  const coursebookAccentColors: Record<string, string> = {
    security: "#581c27", ml: "#312e81", data: "#78350f", web: "#0c4a6e",
    backend: "#14532d", cloud: "#134e4a", code: "#365314", default: "#334155"
  };
  const coursebookAccent = coursebookAccentColors[courseCategory.key] ?? coursebookAccentColors.default;
  const settingsActions: SettingsMenuAction[] = [
    { label: "Modify", icon: "edit", onClick: () => setSettingsOpen(true), disabled: regenerating || deleting },
    { label: regenerating ? "Regenerating…" : "Regenerate", icon: "refresh", onClick: handleRegenerate, disabled: regenerating || deleting },
    { label: deleting ? "Deleting…" : "Delete", icon: "delete", onClick: () => setConfirmDeleteOpen(true), disabled: regenerating || deleting, danger: true },
    // The API 404s this outside local development regardless -- hidden here too so a
    // production build never even shows an action that can't work.
    ...(process.env.NODE_ENV === "development"
      ? [
          { label: "Demo: auto-complete", icon: "smart_toy", onClick: () => setDemoOpen(true) },
          {
            label: clearingDemo ? "Clearing…" : "Demo: clear progress",
            icon: "restart_alt",
            onClick: () => setConfirmClearDemoOpen(true),
            disabled: clearingDemo,
          },
        ]
      : []),
  ];

  return (
    <Box>
      <Breadcrumbs items={[{ label: "My courses", href: "/courses" }, { label: course.title }]} />
      <Stack direction="row" sx={{ alignItems: "flex-start", justifyContent: "space-between", gap: 3, mb: 4 }}>
        <Stack direction="row" sx={{ alignItems: "center", gap: 1.75, minWidth: 0 }}>
          <CourseCategoryBadge title={course.title} goal={course.goal} />
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h4" sx={{ letterSpacing: "-0.02em", mb: 0.5 }}>{course.title}</Typography>
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
          {course.lessons_total > 0 && course.lessons_completed >= course.lessons_total ? (
            <Button
              size="small"
              variant="contained"
              color="secondary"
              startIcon={<Icon name="workspace_premium" />}
              onClick={() => setCertificateOpen(true)}
            >
              Certificate
            </Button>
          ) : null}
          <Button
            size="small"
            variant={course.is_shared ? "contained" : "outlined"}
            color={course.is_shared ? "success" : "primary"}
            startIcon={<Icon name={course.is_shared ? "public" : "share"} />}
            onClick={() => setShareOpen(true)}
          >
            {course.is_shared ? "Shared" : "Share"}
          </Button>
          <SettingsMenu actions={settingsActions} label="Course settings" />
        </Stack>
      </Stack>

      <CourseSettingsDialog course={course} open={settingsOpen} onOpenChange={setSettingsOpen} onSaved={setCourse} />
      <CourseShareDialog course={course} open={shareOpen} onOpenChange={setShareOpen} onSaved={setCourse} />
      <CourseSourcesDialog courseId={courseId} open={sourcesOpen} onOpenChange={setSourcesOpen} />
      <CertificateDialog courseId={courseId} open={certificateOpen} onOpenChange={setCertificateOpen} />
      {process.env.NODE_ENV === "development" ? (
        <DemoAutoCompleteDialog
          courseId={courseId}
          open={demoOpen}
          onOpenChange={setDemoOpen}
          job={demoJob}
          onStart={handleStartDemo}
          onCancel={handleCancelDemo}
        />
      ) : null}
      {process.env.NODE_ENV === "development" && demoJob && demoJob.state === "running" && !demoOpen ? (
        <Alert
          severity="info"
          icon={<CircularProgress size={16} />}
          action={<Button size="small" onClick={() => setDemoOpen(true)}>View</Button>}
          sx={{ mb: 2 }}
        >
          Demo auto-complete still running in the background: {demoJob.completed}/{demoJob.total} concepts done
          {demoJob.current_concept_title ? ` — currently "${demoJob.current_concept_title}"` : ""}.
        </Alert>
      ) : null}

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

      {process.env.NODE_ENV === "development" ? (
        <Dialog open={confirmClearDemoOpen} onClose={() => setConfirmClearDemoOpen(false)}>
          <DialogTitle>Clear demo progress?</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Resets every lesson in &quot;{course.title}&quot; back to never-attempted -- mastery, quiz answers, and
              lab completion all clear. The course content itself is untouched. This cannot be undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button variant="text" onClick={() => setConfirmClearDemoOpen(false)}>Cancel</Button>
            <Button variant="contained" color="error" onClick={handleClearDemo}>Clear progress</Button>
          </DialogActions>
        </Dialog>
      ) : null}

      {progress.stage !== "ready" ? <CourseProgressSteps progress={progress} onResume={handleResumeRemainingLessons} /> : null}
      {refreshError ? <Alert severity="error" sx={{ mb: 2 }}>{refreshError} Retrying automatically…</Alert> : null}
      {deleteError ? <Alert severity="error" sx={{ mb: 2 }}>{deleteError}</Alert> : null}

      {progress.stage === "ready" ? <RecommendationsPanel courseId={courseId} /> : null}

      {progress.stage === "ready" && coursebookConcepts.length > 0 ? (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
          <Box
            sx={{
              position: "relative", overflow: "hidden", mb: 3, p: { xs: 2.25, sm: 3 }, borderRadius: 3,
              color: "white", background: coursebookGradient,
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
                  <Button variant="contained" color="inherit" startIcon={exporting ? <CircularProgress size={16} /> : <Icon name="download" />} onClick={() => void handleExportTextbook()} disabled={exporting} sx={{ color: coursebookAccent, bgcolor: "white", fontWeight: 700, "&:hover": { bgcolor: "#eef2ff" }, "&.Mui-disabled": { color: coursebookAccent, bgcolor: "rgba(255,255,255,0.82)", opacity: 1 }, "& .MuiCircularProgress-root": { color: coursebookAccent } }}>
                    {exporting ? "Preparing PDF…" : "Download coursebook"}
                  </Button>
                  <Button variant="text" startIcon={<Icon name="folder_open" />} onClick={() => setSourcesOpen(true)} sx={{ color: "#e0e7ff" }}>Browse sources</Button>
                </Stack>
              </Stack>
              <Box sx={{ display: { xs: "none", sm: "block" }, alignSelf: "center", flexShrink: 0, perspective: "1000px" }}>
                <Box
                  sx={{
                    position: "relative",
                    width: 156,
                    height: 208,
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    pl: 2.5,
                    pr: 1.75,
                    py: 2.25,
                    color: "#0f172a",
                    borderRadius: "3px 10px 10px 3px",
                    background: "linear-gradient(145deg, #ffffff 0%, #eef2f6 100%)",
                    boxShadow: "0 24px 44px -16px rgba(2, 6, 23, 0.6), 0 10px 20px -12px rgba(2, 6, 23, 0.45)",
                    transform: "rotateY(-14deg)",
                    transformOrigin: "center left",
                    transition: "transform .5s cubic-bezier(.2,.8,.2,1), box-shadow .5s ease",
                    "&:hover": { transform: "rotateY(-5deg)", boxShadow: "0 30px 54px -16px rgba(2, 6, 23, 0.66), 0 12px 22px -12px rgba(2, 6, 23, 0.5)" }
                  }}
                >
                  {/* Spine */}
                  <Box sx={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 11, borderRadius: "3px 0 0 3px", background: `linear-gradient(to right, ${darken(coursebookAccent, 0.28)} 0%, ${coursebookAccent} 72%, rgba(255,255,255,0.55) 100%)` }} />
                  {/* Page fore-edge */}
                  <Box sx={{ position: "absolute", right: 3, top: 12, bottom: 12, width: 4, borderRadius: 0.5, background: "repeating-linear-gradient(to bottom, rgba(148,163,184,0.5) 0 1px, transparent 1px 3px)" }} />
                  <Stack sx={{ gap: 0.85, alignItems: "flex-start" }}>
                    <Box sx={{ width: 30, height: 30, display: "grid", placeItems: "center", borderRadius: 1.5, bgcolor: alpha(coursebookAccent, 0.14), color: coursebookAccent, "& .material-symbol": { fontSize: 18 } }}>
                      <Icon name="menu_book" />
                    </Box>
                    <Typography sx={{ fontSize: "0.5rem", fontWeight: 800, letterSpacing: "0.2em", color: "#64748b" }}>COURSEBOOK</Typography>
                  </Stack>
                  <Stack sx={{ gap: 1 }}>
                    <Typography sx={{ fontWeight: 800, lineHeight: 1.2, fontSize: "0.9rem", letterSpacing: "-0.01em", display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{course.title}</Typography>
                    <Box sx={{ height: 3, width: 32, borderRadius: 2, bgcolor: coursebookAccent }} />
                    <Typography sx={{ fontSize: "0.6rem", fontWeight: 700, letterSpacing: "0.08em", color: "#94a3b8" }}>CANOPY</Typography>
                  </Stack>
                </Box>
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
          <Tab value="practice" icon={<Icon name="fitness_center" />} iconPosition="start" label="Practice" sx={{ minHeight: 36, py: 1, textTransform: "none" }} />
          <Tab value="mastery" icon={<Icon name="insights" />} iconPosition="start" label="Mastery" sx={{ minHeight: 36, py: 1, textTransform: "none" }} />
        </Tabs>
      ) : null}

      {detailTab === "mastery" && progress.stage === "ready" && map.modules.length > 0 ? (
        <MasteryDashboard courseId={courseId} refreshKey={demoJob?.completed} />
      ) : detailTab === "practice" && progress.stage === "ready" && map.modules.length > 0 ? (
        <PracticeDrill courseId={courseId} />
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
