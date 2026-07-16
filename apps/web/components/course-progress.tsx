import { CourseProgressResponse } from "@/lib/api";

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
    steps.push({
      key: "lessons",
      label: `Lessons built (${progress.lessons_built}/${progress.lessons_total})`,
      state: progress.stage === "building_lessons" ? "active" : progress.stage === "ready" ? "done" : "pending"
    });
  }

  return steps;
}

export function CourseProgressSteps({ progress }: { progress: CourseProgressResponse }) {
  const steps = buildSteps(progress);

  return (
    <div className="progress-steps">
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
    </div>
  );
}
