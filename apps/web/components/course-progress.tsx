import { motion } from "motion/react";
import Stack from "@mui/material/Stack";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Stepper from "@mui/material/Stepper";
import Step from "@mui/material/Step";
import StepLabel from "@mui/material/StepLabel";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import Button from "@mui/material/Button";
import { Icon } from "@/components/icon";
import { CourseProgressResponse } from "@/lib/api";
import { useStallDetector } from "@/lib/use-stall-detector";

const stallThresholdMs = 45_000;

type StepState = "done" | "active" | "pending" | "failed";

interface Step {
  key: string;
  label: string;
  state: StepState;
}

function buildSteps(progress: CourseProgressResponse): Step[] {
  const steps: Step[] = [];

  if (progress.sources_total > 0) {
    steps.push({
      key: "sources",
      label: `Sources ready (${progress.sources_ready}/${progress.sources_total})`,
      state: progress.stage === "ingesting_sources" ? "active" : "done"
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
          : "Generating course plan…",
    state: planningState
  });

  if (progress.lessons_total > 0) {
    const lessonsState: StepState = progress.stage === "building_lessons" ? "active" : progress.stage === "ready" ? "done" : "pending";
    const currentLesson = lessonsState === "active" && progress.current_lesson_title ? `, now building "${progress.current_lesson_title}"` : "";
    steps.push({
      key: "lessons",
      label: `Lessons built (${progress.lessons_built}/${progress.lessons_total})${currentLesson}`,
      state: lessonsState
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
    ...(state === "active" && { border: 2, borderColor: "primary.main", color: "primary.main" }),
    ...(state === "pending" && { border: 1, borderColor: "divider", color: "text.secondary" })
  } as const;

  if (state === "active") {
    return (
      <motion.div
        animate={{ boxShadow: ["0 0 0 0 rgba(10,10,10,0.15)", "0 0 0 6px rgba(10,10,10,0)", "0 0 0 0 rgba(10,10,10,0)"] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
        style={{ borderRadius: "50%" }}
      >
        <Box sx={markerSx}>{index + 1}</Box>
      </motion.div>
    );
  }

  return <Box sx={markerSx}>{state === "done" ? <Icon name="check" /> : state === "failed" ? <Icon name="close" /> : index + 1}</Box>;
}

export function CourseProgressSteps({ progress, onResume }: { progress: CourseProgressResponse; onResume?: () => void }) {
  const steps = buildSteps(progress);
  const isActive = progress.stage !== "ready" && progress.stage !== "failed";
  const stallSignature = isActive
    ? `${progress.stage}:${progress.sources_ready}:${progress.lessons_built}:${progress.current_lesson_title ?? ""}`
    : null;
  const stalled = useStallDetector(stallSignature, stallThresholdMs);
  const activeIndex = Math.max(steps.findIndex((step) => step.state === "active"), 0);

  return (
    <Stack sx={{ gap: 2, my: 2 }}>
      {isActive ? (
        <Alert severity="info" icon={false}>
          <Stack direction="row" sx={{ alignItems: "center", gap: 1.5 }}>
            <CircularProgress size={20} />
            <Box>
              <Typography sx={{ fontWeight: 600 }}>
                {progress.stage === "building_lessons" && progress.current_lesson_title
                  ? `Building "${progress.current_lesson_title}"…`
                  : progress.stage === "planning"
                    ? "Generating course plan…"
                    : "Preparing your sources…"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {progress.lessons_total > 0
                  ? `${progress.lessons_built} of ${progress.lessons_total} lessons built so far`
                  : "This updates automatically as work completes."}
              </Typography>
            </Box>
          </Stack>
        </Alert>
      ) : null}

      <Stepper activeStep={activeIndex} orientation="vertical" connector={null}>
        {steps.map((step, index) => (
          <Step key={step.key} completed={step.state === "done"}>
            <StepLabel error={step.state === "failed"} slots={{ stepIcon: () => <StepMarker state={step.state} index={index} /> }}>
              <Typography sx={{ fontWeight: step.state === "active" ? 600 : 400 }}>{step.label}</Typography>
            </StepLabel>
          </Step>
        ))}
      </Stepper>

      {progress.stage === "failed" ? (
        <Alert severity="error">Course planning failed. Use the Regenerate button to try again.</Alert>
      ) : null}

      {stalled && onResume ? (
        <Alert severity="warning" action={<Button color="inherit" size="small" onClick={onResume}>Resume generation</Button>}>
          This is taking longer than expected; generation may have stalled.
        </Alert>
      ) : null}
    </Stack>
  );
}
