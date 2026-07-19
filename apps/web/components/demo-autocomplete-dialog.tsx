"use client";

import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import LinearProgress from "@mui/material/LinearProgress";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import Slider from "@mui/material/Slider";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Typography from "@mui/material/Typography";
import { CourseMapResponse, DemoAutoCompleteOptions, DemoConceptResult, DemoJobStatus, getCourseMap } from "@/lib/api";
import { Icon } from "@/components/icon";
import { conceptKindIcon, conceptKindLabel } from "@/lib/concept-kind";
import { createClient } from "@/lib/supabase/client";

const STATE_LABEL: Record<DemoJobStatus["state"], string> = {
  running: "Running",
  completed: "Completed",
  cancelled: "Cancelled",
  failed: "Failed"
};

const STATE_SEVERITY: Record<DemoJobStatus["state"], "info" | "success" | "warning" | "error"> = {
  running: "info",
  completed: "success",
  cancelled: "warning",
  failed: "error"
};

function resultChip(result: DemoConceptResult) {
  if (result.error) return <Chip size="small" color="error" label={`Error: ${result.error}`} />;
  const parts: string[] = [];
  if (result.quiz_items_correct || result.quiz_items_incorrect || result.quiz_items_skipped) {
    parts.push(`${result.quiz_items_correct} correct, ${result.quiz_items_incorrect} wrong${result.quiz_items_skipped ? `, ${result.quiz_items_skipped} skipped` : ""}`);
  }
  if (result.lab_passed !== null) parts.push(result.lab_passed ? "lab passed" : "lab failed");
  return <Chip size="small" variant="outlined" label={parts.join(" · ") || "not attempted"} />;
}

/** Dev-only: drive some or all of a course to completion (or a deliberately mixed
 *  mastery state) as an LLM standing in for the learner, so mastery/points/completion/
 *  certificate state can be demoed without grinding through a course by hand.
 *
 *  Job state lives in the parent (course-detail.tsx) and keeps polling regardless of
 *  whether this dialog is open, so closing it is just closing a window onto a run that
 *  keeps going on the server -- never a way to stop it. The server 404s every one of
 *  these endpoints outside local development regardless of whether this panel is
 *  reachable in the UI. */
export function DemoAutoCompleteDialog({
  courseId,
  open,
  onOpenChange,
  job,
  onStart,
  onCancel
}: {
  courseId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  job: DemoJobStatus | undefined;
  onStart: (options: DemoAutoCompleteOptions) => Promise<void>;
  onCancel: () => Promise<void>;
}) {
  const [courseMap, setCourseMap] = useState<CourseMapResponse>();
  const [loadingMap, setLoadingMap] = useState(false);
  const [mapError, setMapError] = useState<string>();
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(new Set());
  const [includeQuizzes, setIncludeQuizzes] = useState(true);
  const [includeLabs, setIncludeLabs] = useState(true);
  const [target, setTarget] = useState<"mastered" | "mixed">("mastered");
  const [correctRate, setCorrectRate] = useState(0.6);
  const [starting, setStarting] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [error, setError] = useState<string>();

  const running = job?.state === "running";

  useEffect(() => {
    if (!open || courseMap) return;
    let cancelled = false;

    async function load() {
      setLoadingMap(true);
      setMapError(undefined);
      try {
        const { data } = await createClient().auth.getSession();
        if (!data.session) throw new Error("Your session has expired. Please sign in again.");
        const map = await getCourseMap(courseId, data.session.access_token);
        if (cancelled) return;
        setCourseMap(map);
        setSelectedSlugs(new Set(map.modules.flatMap((module) => module.concepts.map((concept) => concept.slug))));
      } catch (caught) {
        if (!cancelled) setMapError(caught instanceof Error ? caught.message : "Unable to load the course outline.");
      } finally {
        if (!cancelled) setLoadingMap(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [courseId, open, courseMap]);

  const allSlugs = courseMap?.modules.flatMap((module) => module.concepts.map((concept) => concept.slug)) ?? [];

  function toggleSlug(slug: string) {
    setSelectedSlugs((current) => {
      const next = new Set(current);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  async function handleRun() {
    setStarting(true);
    setError(undefined);
    try {
      await onStart({
        target,
        correctRate,
        conceptSlugs: selectedSlugs.size === allSlugs.length ? undefined : Array.from(selectedSlugs),
        includeQuizzes,
        includeLabs
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to start auto-complete.");
    } finally {
      setStarting(false);
    }
  }

  async function handleCancel() {
    setCanceling(true);
    setError(undefined);
    try {
      await onCancel();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to cancel the run.");
    } finally {
      setCanceling(false);
    }
  }

  return (
    <Dialog open={open} onClose={() => onOpenChange(false)} fullWidth maxWidth="sm">
      <DialogTitle>Demo: auto-complete course</DialogTitle>
      <DialogContent>
        <Stack sx={{ gap: 2, pt: 0.5 }}>
          <Typography variant="body2" color="text.secondary">
            Dev-only. Answers quizzes and submits labs as an LLM standing in for the learner, through the real
            grading and sandbox paths.
          </Typography>

          {job ? (
            <Box sx={{ border: 1, borderColor: "divider", borderRadius: 1.5, p: 1.5 }}>
              <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between" }}>
                <Stack direction="row" sx={{ alignItems: "center", gap: 1 }}>
                  {running ? <CircularProgress size={16} /> : null}
                  <Typography sx={{ fontWeight: 700 }}>{STATE_LABEL[job.state]}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {job.completed}/{job.total} concepts
                  </Typography>
                </Stack>
                {running ? (
                  <Button size="small" color="error" variant="outlined" onClick={() => void handleCancel()} loading={canceling}>
                    Cancel run
                  </Button>
                ) : null}
              </Stack>
              <LinearProgress
                variant="determinate"
                value={job.total ? Math.round((job.completed / job.total) * 100) : 0}
                sx={{ my: 1, borderRadius: 1 }}
              />
              {running ? (
                <Typography variant="body2" color="text.secondary">
                  {job.current_concept_title ? `Working on "${job.current_concept_title}"…` : "Working…"} This keeps
                  running in the background even if you close this dialog -- reopen anytime to check on it, or
                  cancel above to stop it before its next concept.
                </Typography>
              ) : null}
              {job.state === "cancelled" ? (
                <Typography variant="body2" color="text.secondary">
                  Stopped before its next concept. Everything finished before that point was graded for real and is
                  reflected below.
                </Typography>
              ) : null}
              {job.error ? <Alert severity={STATE_SEVERITY[job.state]} sx={{ mt: 1 }}>{job.error}</Alert> : null}
              {job.results.length > 0 ? (
                <List disablePadding sx={{ display: "grid", gap: 0.75, mt: 1 }}>
                  {job.results.map((result) => (
                    <ListItem key={result.concept_slug} sx={{ border: 1, borderColor: "divider", borderRadius: 1.5, py: 0.75 }}>
                      <ListItemText primary={result.concept_title} secondary={result.kind} />
                      {resultChip(result)}
                    </ListItem>
                  ))}
                </List>
              ) : null}
            </Box>
          ) : null}

          <Divider />

          <Box sx={{ opacity: running ? 0.5 : 1, pointerEvents: running ? "none" : "auto" }}>
            <Stack sx={{ gap: 2 }}>
              <Box>
                <Typography variant="overline" color="text.secondary">Target mastery</Typography>
                <Tabs value={target} onChange={(_event, value: "mastered" | "mixed") => setTarget(value)}>
                  <Tab value="mastered" label="Fully mastered" sx={{ textTransform: "none" }} />
                  <Tab value="mixed" label="Mixed mastery" sx={{ textTransform: "none" }} />
                </Tabs>
                {target === "mixed" ? (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="body2" gutterBottom>
                      Target correct rate: <strong>{Math.round(correctRate * 100)}%</strong>
                    </Typography>
                    <Slider value={correctRate} onChange={(_event, value) => setCorrectRate(value as number)} min={0} max={1} step={0.1} />
                  </Box>
                ) : null}
              </Box>

              <Box>
                <Typography variant="overline" color="text.secondary">What to auto-complete</Typography>
                <Stack direction="row" sx={{ gap: 2 }}>
                  <FormControlLabel control={<Checkbox checked={includeQuizzes} onChange={(event) => setIncludeQuizzes(event.target.checked)} />} label="Quizzes" />
                  <FormControlLabel control={<Checkbox checked={includeLabs} onChange={(event) => setIncludeLabs(event.target.checked)} />} label="Labs" />
                </Stack>
              </Box>

              <Box>
                <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between" }}>
                  <Typography variant="overline" color="text.secondary">
                    Concepts ({selectedSlugs.size}/{allSlugs.length} selected)
                  </Typography>
                  <Stack direction="row" sx={{ gap: 0.5 }}>
                    <Button size="small" onClick={() => setSelectedSlugs(new Set(allSlugs))}>All</Button>
                    <Button size="small" onClick={() => setSelectedSlugs(new Set())}>None</Button>
                  </Stack>
                </Stack>
                {loadingMap ? (
                  <Stack direction="row" sx={{ alignItems: "center", gap: 1, color: "text.secondary", py: 1 }}>
                    <CircularProgress size={16} /> <Typography variant="body2">Loading course outline…</Typography>
                  </Stack>
                ) : mapError ? (
                  <Alert severity="error">{mapError}</Alert>
                ) : (
                  <Box sx={{ maxHeight: 260, overflowY: "auto", border: 1, borderColor: "divider", borderRadius: 1.5, p: 1 }}>
                    {courseMap?.modules.map((module, index) => (
                      <Box key={module.position} sx={{ mb: index < courseMap.modules.length - 1 ? 1 : 0 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ display: "block", px: 0.5 }}>{module.title}</Typography>
                        {module.concepts.map((concept) => (
                          <FormControlLabel
                            key={concept.slug}
                            sx={{ display: "flex", ml: 0 }}
                            control={<Checkbox size="small" checked={selectedSlugs.has(concept.slug)} onChange={() => toggleSlug(concept.slug)} />}
                            label={
                              <Stack direction="row" sx={{ alignItems: "center", gap: 0.75 }}>
                                <Icon name={conceptKindIcon(concept.kind)} />
                                <Typography variant="body2">{concept.title}</Typography>
                                <Typography variant="caption" color="text.secondary">{conceptKindLabel(concept.kind)}</Typography>
                              </Stack>
                            }
                          />
                        ))}
                        {index < courseMap.modules.length - 1 ? <Divider sx={{ my: 0.75 }} /> : null}
                      </Box>
                    ))}
                  </Box>
                )}
              </Box>
            </Stack>
          </Box>

          {error ? <Alert severity="error">{error}</Alert> : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button variant="text" onClick={() => onOpenChange(false)}>{running ? "Hide (keeps running)" : "Close"}</Button>
        <Button
          variant="contained"
          startIcon={<Icon name="smart_toy" />}
          onClick={() => void handleRun()}
          loading={starting}
          disabled={running || selectedSlugs.size === 0 || (!includeQuizzes && !includeLabs)}
        >
          Run ({selectedSlugs.size})
        </Button>
      </DialogActions>
    </Dialog>
  );
}
