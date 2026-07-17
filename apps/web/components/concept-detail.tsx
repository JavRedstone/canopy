"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { ConceptDetailResponse, CourseSummary, LessonRunResult, LessonWorkspaceFile, QuizItemPreview, ScriptRunResult, WorkedExamplePreview, getConceptDetail, getCourse, regenerateLesson, runLesson, runLessonScript } from "@/lib/api";
import { useFullBleed } from "@/components/app-shell";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { Icon } from "@/components/icon";
import { MarkdownText } from "@/components/markdown-text";
import { QuizQuestion, QuizSection } from "@/components/quiz";
import { SettingsMenu } from "@/components/settings-menu";
import { conceptKindIcon, conceptKindLabel } from "@/lib/concept-kind";
import { createClient } from "@/lib/supabase/client";
import { parsePytestCases } from "@/lib/pytest-output";
import { useStallDetector } from "@/lib/use-stall-detector";
import type { ReactNode } from "react";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });
const stallThresholdMs = 45_000;

// A line the lesson generator emits to place a worked example or quiz item
// inside the prose, e.g. "{{example:1}}" or "{{quiz:2}}" (1-based indexes).
const LESSON_MARKER = /^\s*\{\{\s*(example|quiz)\s*:\s*(\d+)\s*\}\}\s*$/;

function markerReferencedQuizIndexes(markdown: string): Set<number> {
  const referenced = new Set<number>();
  for (const line of markdown.split("\n")) {
    const match = line.match(LESSON_MARKER);
    if (match && match[1] === "quiz") referenced.add(Number(match[2]) - 1);
  }
  return referenced;
}

function WorkedExampleCard({ example, citations }: { example: WorkedExamplePreview; citations?: string[] }) {
  return (
    <div className="notice">
      <strong>{example.title}</strong>
      <MarkdownText citations={citations}>{example.body_markdown}</MarkdownText>
    </div>
  );
}

function WorkedExamples({ examples, citations }: { examples?: WorkedExamplePreview[]; citations?: string[] }) {
  if (!examples?.length) return null;
  return (
    <>
      <div className="lesson-content-divider"><span>Worked examples</span></div>
      {examples.map((example) => (
        <WorkedExampleCard example={example} citations={citations} key={example.title} />
      ))}
    </>
  );
}

/** Lesson prose with worked examples and quiz items rendered at their marker
 *  positions. Unreferenced examples still appear as a trailing section, and
 *  unreferenced quiz items are left for the caller's QuizSection, so lessons
 *  generated before markers existed render exactly as before. */
function LessonBody({
  courseId,
  slug,
  markdown,
  citations,
  examples,
  quizItems,
  quizMaxAttempts,
}: {
  courseId: string;
  slug: string;
  markdown: string;
  citations?: string[];
  examples: WorkedExamplePreview[];
  quizItems: QuizItemPreview[];
  quizMaxAttempts: number;
}) {
  const blocks: ReactNode[] = [];
  const placedExamples = new Set<number>();
  const placedQuiz = new Set<number>();
  let buffer: string[] = [];
  let insideCodeFence = false;
  const flush = () => {
    const text = buffer.join("\n");
    if (text.trim()) blocks.push(<MarkdownText className="lesson-content" citations={citations} key={`text-${blocks.length}`}>{text}</MarkdownText>);
    buffer = [];
  };
  for (const line of markdown.split("\n")) {
    if (line.trimStart().startsWith("```")) insideCodeFence = !insideCodeFence;
    const match = insideCodeFence ? null : line.match(LESSON_MARKER);
    if (!match) {
      buffer.push(line);
      continue;
    }
    const index = Number(match[2]) - 1;
    if (match[1] === "example" && examples[index] && !placedExamples.has(index)) {
      flush();
      placedExamples.add(index);
      blocks.push(<WorkedExampleCard example={examples[index]} citations={citations} key={`example-${index}`} />);
    } else if (match[1] === "quiz" && quizItems[index] && !placedQuiz.has(index)) {
      flush();
      placedQuiz.add(index);
      blocks.push(
        <div className="quiz-inline" key={`quiz-${index}`}>
          <QuizQuestion courseId={courseId} slug={slug} item={quizItems[index]} index={placedQuiz.size - 1} maxAttempts={quizMaxAttempts} />
        </div>
      );
    } else {
      flush();
    }
  }
  flush();
  const leftoverExamples = examples.filter((_, index) => !placedExamples.has(index));
  return (
    <>
      {blocks}
      <WorkedExamples examples={leftoverExamples} citations={citations} />
    </>
  );
}

function defaultScratchScript(starterFiles: LessonWorkspaceFile[]): string {
  const moduleName = starterFiles[0]?.path.replace(/\.py$/, "") ?? "solution";
  return `# Import your solution and try anything - print() shows up below when you run it.\nfrom ${moduleName} import *\n`;
}

export function ConceptDetail({ courseId, slug }: { courseId: string; slug: string }) {
  const [course, setCourse] = useState<CourseSummary>();
  const [concept, setConcept] = useState<ConceptDetailResponse>();
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string>();
  const [files, setFiles] = useState<LessonWorkspaceFile[]>([]);
  const [runResult, setRunResult] = useState<LessonRunResult>();
  const [running, setRunning] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [activeFilePath, setActiveFilePath] = useState<string>();
  const [scratchCode, setScratchCode] = useState("");
  const [scriptResult, setScriptResult] = useState<ScriptRunResult>();
  const [runningScript, setRunningScript] = useState(false);
  const [instructionsTab, setInstructionsTab] = useState<"lesson" | "solution">("lesson");
  const [solutionRevealed, setSolutionRevealed] = useState(false);
  const [consoleTab, setConsoleTab] = useState<"testcase" | "console" | "tests">("testcase");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) return;
      try {
        const token = data.session.access_token;
        const [courseSummary, conceptDetail] = await Promise.all([
          getCourse(courseId, token),
          getConceptDetail(courseId, slug, token)
        ]);
        if (cancelled) return;
        setCourse(courseSummary);
        setConcept(conceptDetail);
        const starterFiles = conceptDetail.lesson?.starter_files ?? [];
        setFiles(starterFiles);
        setActiveFilePath(starterFiles[0]?.path);
        setRunResult(undefined);
        setScriptResult(undefined);
        setScratchCode(defaultScratchScript(starterFiles));
        setInstructionsTab("lesson");
        setSolutionRevealed(false);
        setConsoleTab("testcase");
        setState("ready");
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
    };
  }, [courseId, slug, reloadNonce]);

  const lessonStatus = concept?.lesson?.status;
  const generationStatus = concept?.generation_status ?? lessonStatus;
  const isBuildPending = generationStatus === "pending" || generationStatus === "building";

  useEffect(() => {
    if (!isBuildPending) return;
    const timer = window.setTimeout(() => setReloadNonce((current) => current + 1), 3000);
    return () => window.clearTimeout(timer);
  }, [isBuildPending]);

  function updateFile(path: string, content: string) {
    setFiles((current) => current.map((file) => file.path === path ? { ...file, content } : file));
  }

  const stallSignature = isBuildPending ? (generationStatus ?? "queued") : null;
  const stalled = useStallDetector(stallSignature, stallThresholdMs);

  // A coding lab is a workspace, not an article -- give it the whole viewport instead of
  // boxing the editor into the same centered reading column as prose lessons.
  useFullBleed(concept?.kind === "coding");

  const publicTestFiles = concept?.lesson?.public_test_files ?? [];
  const activeEditableFile = files.find((file) => file.path === activeFilePath);
  const activePublicTestFile = publicTestFiles.find((file) => file.path === activeFilePath);
  const activeFile = activeEditableFile ?? activePublicTestFile ?? files[0];
  const activeFileIsReadOnly = !activeEditableFile;

  async function handleRun() {
    setConsoleTab("tests");
    setRunning(true);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      setErrorMessage(undefined);
      setRunResult(await runLesson(courseId, slug, files, data.session.access_token));
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Unable to run exercise tests.");
    } finally {
      setRunning(false);
    }
  }

  async function handleRunScript() {
    setConsoleTab("console");
    setRunningScript(true);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      setErrorMessage(undefined);
      setScriptResult(
        await runLessonScript(courseId, slug, files, { path: "scratch.py", content: scratchCode }, data.session.access_token)
      );
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Unable to run your script.");
    } finally {
      setRunningScript(false);
    }
  }

  async function handleRegenerateLesson() {
    setRegenerating(true);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      await regenerateLesson(courseId, slug, data.session.access_token);
      setErrorMessage(undefined);
      setConcept((current) => current ? {
        ...current,
        generation_status: "pending",
        lesson: current.lesson ? { ...current.lesson, status: "pending" } : null,
      } : current);
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Unable to regenerate this lesson.");
    } finally {
      setRegenerating(false);
    }
  }

  if (state === "loading") return <div className="shell"><p className="muted">Loading…</p></div>;
  if (state === "error") return <div className="shell"><p className="error">{errorMessage ?? "We could not load this concept."}</p></div>;
  if (!course || !concept) return null;

  const breadcrumbs = (
    <Breadcrumbs
      items={[
        { label: "My courses", href: "/courses" },
        { label: course.title, href: `/courses/${courseId}` },
        { label: concept.title }
      ]}
    />
  );

  if (concept.kind !== "coding") {
    return (
      <div className="shell">
        {breadcrumbs}
        <header className="page-header">
          <div className="course-row-main">
            <span className="concept-kind-badge">
              <Icon name={conceptKindIcon(concept.kind)} />
            </span>
            <div>
              <span className="eyebrow">{conceptKindLabel(concept.kind)}</span>
              <h1>{concept.title}</h1>
            </div>
          </div>
          <SettingsMenu actions={[{ label: regenerating ? "Regenerating…" : "Regenerate lesson", icon: "refresh", onClick: handleRegenerateLesson, disabled: regenerating }]} label="Lesson settings" />
        </header>

        <MarkdownText citations={concept.citations}>{concept.summary_markdown}</MarkdownText>
        {errorMessage ? <p className="error">{errorMessage}</p> : null}

        {isBuildPending ? (
          <div className="building-banner">
            <span className="spinner spinner-large" aria-hidden="true" />
            <span>{generationStatus === "building" ? "Regenerating this lesson…" : "Lesson regeneration is queued…"}<span className="building-banner-detail">This page refreshes automatically when the worker finishes.</span></span>
          </div>
        ) : null}

        {generationStatus === "failed" ? <p className="error">Lesson generation failed. Use Regenerate lesson to retry.</p> : null}

        {!isBuildPending && concept.lesson?.status === "built" && concept.lesson.explanation_markdown ? (
          <div className="lesson-preview">
            <div className="lesson-content-divider"><span>Lesson</span></div>
            <LessonBody
              courseId={courseId}
              slug={slug}
              markdown={concept.lesson.explanation_markdown}
              citations={concept.citations}
              examples={concept.lesson.worked_examples ?? []}
              quizItems={concept.lesson.quiz_items ?? []}
              quizMaxAttempts={concept.lesson.quiz_max_attempts}
            />
            <QuizSection
              courseId={courseId}
              slug={slug}
              items={(concept.lesson.quiz_items ?? []).filter(
                (_, index) => !markerReferencedQuizIndexes(concept.lesson?.explanation_markdown ?? "").has(index)
              )}
              maxAttempts={concept.lesson.quiz_max_attempts}
            />
          </div>
        ) : null}
      </div>
    );
  }

  const lab = (
    <div className="lab-shell">
      <div className="lab-topbar">
        <div className="lab-topbar-left">
          {breadcrumbs}
          <div className="course-row-main">
            <span className="concept-kind-badge">
              <Icon name={conceptKindIcon(concept.kind)} />
            </span>
            <div>
              <span className="eyebrow">{conceptKindLabel(concept.kind)}</span>
              <h1>{concept.title}</h1>
            </div>
          </div>
        </div>
        <SettingsMenu actions={[{ label: regenerating ? "Regenerating…" : "Regenerate lesson", icon: "refresh", onClick: handleRegenerateLesson, disabled: regenerating }]} label="Lesson settings" />
      </div>

      {errorMessage ? <p className="error lab-inline-error">{errorMessage}</p> : null}

      {concept.lesson && concept.lesson.status === "built" ? (
        <div className="lab-body">
          <div className="lab-instructions">
            <div className="lab-instructions-tabs" role="tablist" aria-label="Instructions">
              <button className="lab-instructions-tab" type="button" role="tab" data-active={instructionsTab === "lesson" || undefined} aria-selected={instructionsTab === "lesson"} onClick={() => setInstructionsTab("lesson")}>Lesson</button>
              {concept.lesson.solution_files.length > 0 ? (
                <button className="lab-instructions-tab" type="button" role="tab" data-active={instructionsTab === "solution" || undefined} aria-selected={instructionsTab === "solution"} onClick={() => setInstructionsTab("solution")}>Solution</button>
              ) : null}
            </div>

            {instructionsTab === "lesson" ? (
              <>
                <MarkdownText citations={concept.citations}>{concept.summary_markdown}</MarkdownText>

                {concept.lesson.explanation_markdown ? <>
                  <div className="lesson-content-divider"><span>Lesson</span></div>
                  <LessonBody
                    courseId={courseId}
                    slug={slug}
                    markdown={concept.lesson.explanation_markdown}
                    citations={concept.citations}
                    examples={concept.lesson.worked_examples ?? []}
                    quizItems={concept.lesson.quiz_items ?? []}
                    quizMaxAttempts={concept.lesson.quiz_max_attempts}
                  />
                </> : <WorkedExamples examples={concept.lesson.worked_examples} citations={concept.citations} />}

                {concept.lesson.hints.length > 0 ? (
                  <div className="notice">
                    <strong>Hints</strong>
                    <ul>
                      {concept.lesson.hints.map((hint, index) => (
                        <li key={index}>{hint}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <QuizSection
                  courseId={courseId}
                  slug={slug}
                  items={(concept.lesson.quiz_items ?? []).filter(
                    (_, index) => !markerReferencedQuizIndexes(concept.lesson?.explanation_markdown ?? "").has(index)
                  )}
                  maxAttempts={concept.lesson.quiz_max_attempts}
                />
              </>
            ) : !solutionRevealed ? (
              <div className="lab-solution-gate">
                <p className="muted">Seeing the reference solution before you&apos;ve solved it yourself will spoil the exercise.</p>
                <button className="button button-secondary" type="button" onClick={() => setSolutionRevealed(true)}>Show solution</button>
              </div>
            ) : (
              <div className="lab-solution-files">
                {concept.lesson.solution_files.map((file) => (
                  <div className="lab-solution-file" key={file.path}>
                    <div className="lab-solution-file-name">{file.path}</div>
                    <MonacoEditor
                      height={`${Math.min(Math.max(file.content.split("\n").length * 19 + 20, 100), 480)}px`}
                      language="python"
                      theme="vs-dark"
                      path={`solution/${file.path}`}
                      value={file.content}
                      options={{ minimap: { enabled: false }, fontSize: 12, tabSize: 4, readOnly: true, domReadOnly: true, scrollBeyondLastLine: false, scrollbar: { alwaysConsumeMouseWheel: false, verticalScrollbarSize: 10, horizontalScrollbarSize: 10 } }}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="lab-workspace-pane">
            <div className="lab-workspace-toolbar">
              <div className="lesson-file-tabs" role="tablist" aria-label="Lesson files">
                {files.map((file) => (
                  <button className="lesson-file-tab" data-active={activeFile?.path === file.path || undefined} type="button" role="tab" aria-selected={activeFile?.path === file.path} onClick={() => setActiveFilePath(file.path)} key={file.path}>
                    <Icon name="code" className="lesson-file-tab-icon" />{file.path}
                  </button>
                ))}
                {publicTestFiles.map((file) => (
                  <button className="lesson-file-tab lesson-file-tab-readonly" data-active={activeFile?.path === file.path || undefined} type="button" role="tab" aria-selected={activeFile?.path === file.path} onClick={() => setActiveFilePath(file.path)} key={file.path}>
                    <Icon name="lock" className="lesson-file-tab-icon" />{file.path}
                  </button>
                ))}
              </div>
              <div className="lab-workspace-actions">
                <button className="lab-run-btn" type="button" onClick={handleRunScript} disabled={runningScript}>
                  <Icon name="play_arrow" />{runningScript ? "Running…" : "Run"}
                </button>
                <button className="lab-submit-btn" type="button" onClick={handleRun} disabled={running}>
                  <Icon name="play_arrow" />{running ? "Submitting…" : "Submit"}
                </button>
              </div>
            </div>
            {activeFileIsReadOnly ? <p className="muted lab-readonly-hint">This is one of the checks your solution is graded against (read-only, but always included when you Submit).</p> : null}
            <div className="lab-editor-wrap">
              {activeFile ? (
                <MonacoEditor
                  height="100%"
                  language="python"
                  theme="vs-dark"
                  path={activeFile.path}
                  value={activeFile.content}
                  onChange={(content) => { if (!activeFileIsReadOnly) updateFile(activeFile.path, content ?? ""); }}
                  options={{ minimap: { enabled: false }, fontSize: 12, tabSize: 4, automaticLayout: true, scrollBeyondLastLine: false, readOnly: activeFileIsReadOnly, scrollbar: { alwaysConsumeMouseWheel: false, verticalScrollbarSize: 10, horizontalScrollbarSize: 10 } }}
                />
              ) : null}
            </div>

            <div className="lab-console-panel">
              <div className="lab-console-tabs" role="tablist" aria-label="Testcase, console, and test results">
                <button className="lab-console-tab" type="button" role="tab" data-active={consoleTab === "testcase" || undefined} aria-selected={consoleTab === "testcase"} onClick={() => setConsoleTab("testcase")}>
                  <Icon name="edit_note" /> Testcase
                </button>
                <button className="lab-console-tab" type="button" role="tab" data-active={consoleTab === "console" || undefined} aria-selected={consoleTab === "console"} onClick={() => setConsoleTab("console")}>
                  <Icon name="terminal" /> Console{scriptResult ? <span className={`lab-console-tab-dot ${scriptResult.exit_code === 0 && !scriptResult.timed_out ? "passed" : "failed"}`} /> : null}
                </button>
                <button className="lab-console-tab" type="button" role="tab" data-active={consoleTab === "tests" || undefined} aria-selected={consoleTab === "tests"} onClick={() => setConsoleTab("tests")}>
                  <Icon name="fact_check" /> Test Result{runResult ? <span className={`lab-console-tab-dot ${runResult.passed ? "passed" : "failed"}`} /> : null}
                </button>
              </div>
              <div className="lab-console-body">
                {consoleTab === "testcase" ? (
                  <>
                    <span className="muted">Edit this script to call your code with whatever input you want, then hit Run to see what it prints. Never affects grading.</span>
                    <MonacoEditor
                      height="150px"
                      language="python"
                      theme="vs-dark"
                      path="scratch.py"
                      value={scratchCode}
                      onChange={(content) => setScratchCode(content ?? "")}
                      options={{ minimap: { enabled: false }, fontSize: 12, tabSize: 4, automaticLayout: true, scrollBeyondLastLine: false, scrollbar: { alwaysConsumeMouseWheel: false, verticalScrollbarSize: 10, horizontalScrollbarSize: 10 } }}
                    />
                  </>
                ) : consoleTab === "console" ? (
                  scriptResult ? (
                    <pre className={`lesson-run-output ${scriptResult.exit_code === 0 && !scriptResult.timed_out ? "passed" : "failed"}`}>
                      {scriptResult.output || "(no output)"}
                      {scriptResult.timed_out ? "\n\n[timed out]" : scriptResult.exit_code !== 0 ? `\n\n[exited with code ${scriptResult.exit_code}]` : ""}
                    </pre>
                  ) : (
                    <p className="muted">Edit your script on the Testcase tab, then hit Run above to see its output here.</p>
                  )
                ) : runResult ? (
                  <>
                    <span className="muted">Submit swaps in the full test suite, including hidden checks you can&apos;t see, to validate your solution.</span>
                    {(() => {
                      const cases = parsePytestCases(runResult.output);
                      return cases.length > 0 ? (
                        <ul className="lab-testcase-list">
                          {cases.map((testCase, index) => (
                            <li className={`lab-testcase-row ${testCase.status}`} key={index}>
                              <Icon name={testCase.status === "passed" ? "check_circle" : testCase.status === "skipped" ? "remove_circle" : "cancel"} />
                              <span>{testCase.name}</span>
                            </li>
                          ))}
                        </ul>
                      ) : null;
                    })()}
                    <details className="lab-output-details">
                      <summary>Full output</summary>
                      <pre className={`lesson-run-output ${runResult.passed ? "passed" : "failed"}`}>{runResult.output}</pre>
                    </details>
                  </>
                ) : (
                  <p className="muted">Hit Submit above to see check results here.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : concept.lesson?.status === "failed" ? (
        <div className="lab-empty-state">
          <div>
            <p className="error">This lab could not be built.</p>
            <button className="button button-secondary" type="button" onClick={handleRegenerateLesson} disabled={regenerating}>
              {regenerating ? "Regenerating…" : "Try again"}
            </button>
          </div>
        </div>
      ) : (
        <div className="lab-empty-state">
          <div>
            <div className="building-banner">
              <span className="spinner spinner-large" aria-hidden="true" />
              <span>
                {lessonStatus === "building" ? "Building this lab…" : "Queued to build…"}
                <span className="building-banner-detail">This page updates automatically as soon as it&apos;s ready.</span>
              </span>
            </div>
            {stalled ? (
              <div className="stall-notice">
                <span>This is taking longer than expected; the build may have stalled.</span>
                <button className="button button-secondary" type="button" onClick={handleRegenerateLesson} disabled={regenerating}>
                  {regenerating ? "Resuming…" : "Resume build"}
                </button>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );

  return lab;
}
