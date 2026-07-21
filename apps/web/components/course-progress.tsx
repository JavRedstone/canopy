import { motion } from "motion/react";
import Stack from "@mui/material/Stack";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import LinearProgress from "@mui/material/LinearProgress";
import { alpha } from "@mui/material/styles";
import { CanopyGrowMark } from "@/components/canopy-loader";
import { Icon } from "@/components/icon";
import { CourseProgressResponse } from "@/lib/api";
import { useStallDetector } from "@/lib/use-stall-detector";
import { CANOPY_GREEN } from "@/lib/palette";

// A lesson build can include an LLM call, a sandbox run, and a repair pass. The
// generation queue keeps its claim for five minutes, so showing Resume after
// only 45 seconds creates a misleading "stalled" state while normal work is
// still in progress.
const stallThresholdMs = 6 * 60_000;

type StepState = "done" | "active" | "pending" | "failed";

interface BuildStep {
  key: string;
  label: string;
  /** What this stage actually does. The bare counts never explained the work being done. */
  detail: string;
  state: StepState;
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function buildSteps(progress: CourseProgressResponse): BuildStep[] {
  const steps: BuildStep[] = [];

  if (progress.sources_total > 0) {
    const active = progress.stage === "ingesting_sources";
    steps.push({
      key: "sources",
      label: active ? "Reading your sources" : "Sources ready",
      detail: active
        ? `${progress.sources_ready} of ${progress.sources_total} read and split into searchable passages`
        : `${plural(progress.sources_total, "document")} split into searchable passages`,
      state: active ? "active" : "done"
    });
  }

  const planningState: StepState =
    progress.stage === "failed"
      ? "failed"
      : progress.stage === "ingesting_sources" || progress.stage === "planning"
        ? "active"
        : "done";
  steps.push({
    key: "planning",
    label:
      planningState === "failed"
        ? "Course plan generation failed"
        : planningState === "done"
          ? "Course plan generated"
          : "Generating course plan",
    detail:
      planningState === "failed"
        ? "Stopped before the plan was complete."
        : planningState === "done"
          ? progress.lessons_total > 0
            ? `${plural(progress.lessons_total, "concept")} mapped out in teaching order`
            : "Concepts mapped out in teaching order"
          : "Working out which concepts to cover, and the order to teach them in",
    state: planningState
  });

  if (progress.lessons_total > 0) {
    const state: StepState = progress.stage === "building_lessons" ? "active" : progress.stage === "ready" ? "done" : "pending";
    steps.push({
      key: "lessons",
      label: state === "done" ? "Lessons built" : "Building lessons",
      detail:
        state === "done"
          ? "Every lesson written and its exercises validated"
          : state === "active"
            ? progress.current_lesson_title
              ? `Now on "${progress.current_lesson_title}"`
              : "Working through the remaining lessons"
            : "Each lesson is written, then its exercises are checked against their own tests",
      state
    });
  }

  return steps;
}

function StepMarker({ state, index }: { state: StepState; index: number }) {
  const markerSx = {
    width: 28,
    height: 28,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "0.8rem",
    fontWeight: 700,
    flexShrink: 0,
    ...(state === "done" && { bgcolor: "success.main", color: "success.contrastText" }),
    ...(state === "failed" && { bgcolor: "error.main", color: "error.contrastText" }),
    ...(state === "active" && { border: 2, borderColor: CANOPY_GREEN, color: CANOPY_GREEN }),
    ...(state === "pending" && { border: 1, borderColor: "divider", color: "text.secondary" })
  } as const;

  if (state === "active") {
    return (
      <motion.div
        animate={{
          boxShadow: [
            `0 0 0 0 ${alpha(CANOPY_GREEN, 0.35)}`,
            `0 0 0 6px ${alpha(CANOPY_GREEN, 0)}`,
            `0 0 0 0 ${alpha(CANOPY_GREEN, 0)}`
          ]
        }}
        transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
        style={{ borderRadius: "50%" }}
      >
        <Box sx={markerSx}>{index + 1}</Box>
      </motion.div>
    );
  }

  return <Box sx={markerSx}>{state === "done" ? <Icon name="check" /> : state === "failed" ? <Icon name="close" /> : index + 1}</Box>;
}

function headline(progress: CourseProgressResponse): string {
  if (progress.stage === "failed") return "Course generation failed";
  if (progress.stage === "building_lessons") return "Writing your lessons";
  if (progress.stage === "planning") return "Planning your course";
  return "Preparing your sources";
}

export function CourseProgressSteps({ progress, onResume }: { progress: CourseProgressResponse; onResume?: () => void }) {
  const steps = buildSteps(progress);
  const isActive = progress.stage !== "ready" && progress.stage !== "failed";
  const stallSignature = isActive
    ? `${progress.stage}:${progress.sources_ready}:${progress.lessons_built}:${progress.current_lesson_title ?? ""}`
    : null;
  const stalled = useStallDetector(stallSignature, stallThresholdMs);
  const showBar = progress.lessons_total > 0;
  const percent = showBar ? Math.min((progress.lessons_built / progress.lessons_total) * 100, 100) : 0;

  return (
    <Paper variant="outlined" sx={{ my: 2, p: { xs: 2, sm: 3 }, borderRadius: 2 }}>
      <Stack direction="row" sx={{ alignItems: "center", gap: 2 }}>
        {isActive ? <CanopyGrowMark size={44} /> : null}
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h6" sx={{ letterSpacing: "-0.01em" }}>{headline(progress)}</Typography>
          <Typography variant="body2" color="text.secondary">
            {isActive
              ? "This updates on its own. It is safe to close this page, and building carries on."
              : "Nothing already built is lost. Use Regenerate to try again."}
          </Typography>
        </Box>
      </Stack>

      {showBar ? (
        <Box sx={{ mt: 2.5 }}>
          <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "baseline", mb: 0.75 }}>
            <Typography variant="body2" color="text.secondary">Lessons built</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{progress.lessons_built} of {progress.lessons_total}</Typography>
          </Stack>
          <LinearProgress
            variant="determinate"
            value={percent}
            sx={{ height: 6, borderRadius: 999, bgcolor: "action.hover", "& .MuiLinearProgress-bar": { borderRadius: 999 } }}
          />
        </Box>
      ) : null}

      <Box sx={{ mt: 3 }}>
        {steps.map((step, index) => {
          const last = index === steps.length - 1;
          return (
            <Stack key={step.key} direction="row" sx={{ gap: 1.75, alignItems: "stretch" }}>
              {/* Marker plus a connecting rail. The old Stepper passed connector={null}, which
                  left these reading as unordered circles rather than one sequence. */}
              <Stack sx={{ alignItems: "center" }}>
                <StepMarker state={step.state} index={index} />
                {!last ? (
                  <Box sx={{ flex: 1, width: 2, my: 0.5, borderRadius: 1, bgcolor: step.state === "done" ? "success.main" : "divider" }} />
                ) : null}
              </Stack>
              <Box sx={{ pb: last ? 0 : 2.5, minWidth: 0 }}>
                <Typography sx={{ fontWeight: step.state === "active" ? 600 : 500, lineHeight: 1.4 }}>{step.label}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>{step.detail}</Typography>
              </Box>
            </Stack>
          );
        })}
      </Box>

      {/* No separate failure alert: the headline, its sub-line and the failed step already
          say it. A third copy was the same redundancy this card set out to remove. */}
      {stalled && onResume ? (
        <Alert severity="warning" sx={{ mt: 2 }} action={<Button color="inherit" size="small" onClick={onResume}>Resume</Button>}>
          This is taking longer than expected. Resuming only requeues incomplete lessons; it keeps every completed lesson.
        </Alert>
      ) : null}
    </Paper>
  );
}
