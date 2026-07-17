"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { ConceptDetailResponse, CourseSummary, LessonRunResult, LessonWorkspaceFile, QuizItemPreview, ScriptRunResult, WorkedExamplePreview, getConceptDetail, getCourse, regenerateLesson, runLesson, runLessonScript } from "@/lib/api";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { Icon } from "@/components/icon";
import { MarkdownText } from "@/components/markdown-text";
import { QuizQuestion, QuizSection } from "@/components/quiz";
import { conceptKindIcon, conceptKindLabel } from "@/lib/concept-kind";
import { createClient } from "@/lib/supabase/client";
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
}: {
  courseId: string;
  slug: string;
  markdown: string;
  citations?: string[];
  examples: WorkedExamplePreview[];
  quizItems: QuizItemPreview[];
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
          <QuizQuestion courseId={courseId} slug={slug} item={quizItems[index]} index={placedQuiz.size - 1} retryable />
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

  const publicTestFiles = concept?.lesson?.public_test_files ?? [];
  const activeEditableFile = files.find((file) => file.path === activeFilePath);
  const activePublicTestFile = publicTestFiles.find((file) => file.path === activeFilePath);
  const activeFile = activeEditableFile ?? activePublicTestFile ?? files[0];
  const activeFileIsReadOnly = !activeEditableFile;

  async function handleRun() {
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

  if (state === "loading") return <p className="muted">Loading…</p>;
  if (state === "error") return <p className="error">{errorMessage ?? "We could not load this concept."}</p>;
  if (!course || !concept) return null;

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "My courses", href: "/courses" },
          { label: course.title, href: `/courses/${courseId}` },
          { label: concept.title }
        ]}
      />
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
        <button className="button button-secondary" type="button" onClick={handleRegenerateLesson} disabled={regenerating}>{regenerating ? "Regenerating…" : "Regenerate lesson"}</button>
      </header>

      <MarkdownText citations={concept.citations}>{concept.summary_markdown}</MarkdownText>
      {errorMessage ? <p className="error">{errorMessage}</p> : null}

      {concept.kind === "conceptual" && isBuildPending ? (
        <div className="building-banner">
          <span className="spinner spinner-large" aria-hidden="true" />
          <span>{generationStatus === "building" ? "Regenerating this lesson…" : "Lesson regeneration is queued…"}<span className="building-banner-detail">This page refreshes automatically when the worker finishes.</span></span>
        </div>
      ) : null}

      {concept.kind === "conceptual" && generationStatus === "failed" ? <p className="error">Lesson generation failed. Use Regenerate lesson to retry.</p> : null}

      {concept.kind === "conceptual" && !isBuildPending && concept.lesson?.status === "built" && concept.lesson.explanation_markdown ? (
        <div className="lesson-preview">
          <div className="lesson-content-divider"><span>Lesson</span></div>
          <LessonBody
            courseId={courseId}
            slug={slug}
            markdown={concept.lesson.explanation_markdown}
            citations={concept.citations}
            examples={concept.lesson.worked_examples ?? []}
            quizItems={concept.lesson.quiz_items ?? []}
          />
          <QuizSection
            courseId={courseId}
            slug={slug}
            items={(concept.lesson.quiz_items ?? []).filter(
              (_, index) => !markerReferencedQuizIndexes(concept.lesson?.explanation_markdown ?? "").has(index)
            )}
          />
        </div>
      ) : null}

      {concept.kind === "coding" ? (
        concept.lesson && concept.lesson.status === "built" ? (
          <div className="lesson-preview">
            {concept.lesson.explanation_markdown ? <>
              <div className="lesson-content-divider"><span>Lesson</span></div>
              <LessonBody
                courseId={courseId}
                slug={slug}
                markdown={concept.lesson.explanation_markdown}
                citations={concept.citations}
                examples={concept.lesson.worked_examples ?? []}
                quizItems={concept.lesson.quiz_items ?? []}
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

            <div className="lesson-workspace">
              <div className="lesson-file-tabs" role="tablist" aria-label="Lesson files">
                {files.map((file) => <button className="lesson-file-tab" data-active={activeFile?.path === file.path || undefined} type="button" role="tab" aria-selected={activeFile?.path === file.path} onClick={() => setActiveFilePath(file.path)} key={file.path}>{file.path}</button>)}
                {publicTestFiles.map((file) => <button className="lesson-file-tab lesson-file-tab-readonly" data-active={activeFile?.path === file.path || undefined} type="button" role="tab" aria-selected={activeFile?.path === file.path} onClick={() => setActiveFilePath(file.path)} key={file.path}>{file.path} <span className="muted">(test)</span></button>)}
              </div>
              {activeFileIsReadOnly ? <p className="muted">This is one of the checks your solution is graded against — read-only, but always runs as part of &quot;Run checks&quot;.</p> : null}
              {activeFile ? (
                <MonacoEditor
                  height="420px"
                  language="python"
                  theme="vs-dark"
                  path={activeFile.path}
                  value={activeFile.content}
                  onChange={(content) => { if (!activeFileIsReadOnly) updateFile(activeFile.path, content ?? ""); }}
                  options={{ minimap: { enabled: false }, fontSize: 14, tabSize: 4, automaticLayout: true, scrollBeyondLastLine: false, readOnly: activeFileIsReadOnly }}
                />
              ) : null}
            </div>
            <div className="lesson-actions"><button className="button" type="button" onClick={handleRun} disabled={running}>{running ? "Running checks…" : "Run checks"}</button></div>
            {runResult ? <pre className={`lesson-run-output ${runResult.passed ? "passed" : "failed"}`}>{runResult.output}</pre> : null}

            <div className="lesson-console">
              <div className="lesson-console-header">
                <strong>Console</strong>
                <span className="muted">Run any Python here against your current solution and see exactly what it prints. This never affects grading.</span>
              </div>
              <MonacoEditor
                height="180px"
                language="python"
                theme="vs-dark"
                path="scratch.py"
                value={scratchCode}
                onChange={(content) => setScratchCode(content ?? "")}
                options={{ minimap: { enabled: false }, fontSize: 13, tabSize: 4, automaticLayout: true, scrollBeyondLastLine: false }}
              />
              <div className="lesson-actions"><button className="button button-secondary" type="button" onClick={handleRunScript} disabled={runningScript}>{runningScript ? "Running…" : "Run"}</button></div>
              {scriptResult ? (
                <pre className={`lesson-run-output ${scriptResult.exit_code === 0 && !scriptResult.timed_out ? "passed" : "failed"}`}>
                  {scriptResult.output || "(no output)"}
                  {scriptResult.timed_out ? "\n\n[timed out]" : scriptResult.exit_code !== 0 ? `\n\n[exited with code ${scriptResult.exit_code}]` : ""}
                </pre>
              ) : null}
            </div>
            <QuizSection
              courseId={courseId}
              slug={slug}
              items={(concept.lesson.quiz_items ?? []).filter(
                (_, index) => !markerReferencedQuizIndexes(concept.lesson?.explanation_markdown ?? "").has(index)
              )}
            />
          </div>
        ) : concept.lesson?.status === "failed" ? (
          <div>
            <p className="error">This lab could not be built.</p>
            <button className="button button-secondary" type="button" onClick={handleRegenerateLesson} disabled={regenerating}>
              {regenerating ? "Regenerating…" : "Try again"}
            </button>
          </div>
        ) : (
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
                <span>This is taking longer than expected — the build may have stalled.</span>
                <button className="button button-secondary" type="button" onClick={handleRegenerateLesson} disabled={regenerating}>
                  {regenerating ? "Resuming…" : "Resume build"}
                </button>
              </div>
            ) : null}
          </div>
        )
      ) : null}
    </div>
  );
}
