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

export function CourseProgressSteps({ progress, onResume }: { progress: CourseProgressResponse; onResume?: () => void }) {
  const steps = buildSteps(progress);
  const isActive = progress.stage !== "ready" && progress.stage !== "failed";
  const stallSignature = isActive
    ? `${progress.stage}:${progress.sources_ready}:${progress.lessons_built}:${progress.current_lesson_title ?? ""}`
    : null;
  const stalled = useStallDetector(stallSignature, stallThresholdMs);

  return (
    <div className="progress-steps">
      {isActive ? (
        <div className="building-banner">
          <span className="spinner spinner-large" aria-hidden="true" />
          <span>
            {progress.stage === "building_lessons" && progress.current_lesson_title
              ? `Building "${progress.current_lesson_title}"…`
              : progress.stage === "planning"
                ? "Generating course plan…"
                : "Preparing your sources…"}
            <span className="building-banner-detail">
              {progress.lessons_total > 0
                ? `${progress.lessons_built} of ${progress.lessons_total} lessons built so far`
                : "This updates automatically as work completes."}
            </span>
          </span>
        </div>
      ) : null}

      {steps.map((step, index) => (
        <div className={`progress-step progress-step-${step.state}`} key={step.key}>
          <span className="progress-step-marker">
            {step.state === "done" ? "✓" : step.state === "failed" ? "!" : index + 1}
          </span>
          <span className="progress-step-label">{step.label}</span>
        </div>
      ))}
      {progress.stage === "failed" ? (
        <p className="error">Course planning failed. Use the Regenerate button to try again.</p>
      ) : null}
      {stalled && onResume ? (
        <div className="stall-notice">
          <span>This is taking longer than expected; generation may have stalled.</span>
          <button className="button button-secondary" type="button" onClick={onResume}>Resume generation</button>
        </div>
      ) : null}
    </div>
  );
}
