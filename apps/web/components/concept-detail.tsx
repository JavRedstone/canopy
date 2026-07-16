"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { ConceptDetailResponse, CourseSummary, LessonRunResult, LessonWorkspaceFile, getConceptDetail, getCourse, regenerateLesson, runLesson } from "@/lib/api";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { Icon } from "@/components/icon";
import { MarkdownText } from "@/components/markdown-text";
import { conceptKindIcon, conceptKindLabel } from "@/lib/concept-kind";
import { createClient } from "@/lib/supabase/client";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

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
        setFiles(conceptDetail.lesson?.starter_files ?? []);
        setActiveFilePath(conceptDetail.lesson?.starter_files[0]?.path);
        setRunResult(undefined);
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

  useEffect(() => {
    const lessonStatus = concept?.lesson?.status;
    if (lessonStatus !== "pending" && lessonStatus !== "building") return;
    const timer = window.setTimeout(() => setReloadNonce((current) => current + 1), 3000);
    return () => window.clearTimeout(timer);
  }, [concept?.lesson?.status]);

  function updateFile(path: string, content: string) {
    setFiles((current) => current.map((file) => file.path === path ? { ...file, content } : file));
  }

  const activeFile = files.find((file) => file.path === activeFilePath) ?? files[0];

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

  async function handleRegenerateLesson() {
    setRegenerating(true);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      await regenerateLesson(courseId, slug, data.session.access_token);
      setErrorMessage(undefined);
      setConcept((current) => current?.lesson ? { ...current, lesson: { ...current.lesson, status: "pending" } } : current);
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

      <MarkdownText>{concept.summary_markdown}</MarkdownText>
      {errorMessage ? <p className="error">{errorMessage}</p> : null}

      {concept.kind === "coding" ? (
        concept.lesson && concept.lesson.status === "built" ? (
          <div className="lesson-preview">
            {concept.lesson.explanation_markdown ? <MarkdownText className="muted">{concept.lesson.explanation_markdown}</MarkdownText> : null}

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

            {concept.lesson.public_test_cases.length > 0 ? (
              <div className="lesson-checks">
                <strong>What your solution is checked for</strong>
                <ul>
                  {concept.lesson.public_test_cases.map((testCase) => <li key={testCase.name}><strong>{testCase.name}:</strong> {testCase.description}</li>)}
                </ul>
                <span className="muted">Additional edge-case checks stay private to keep the exercise meaningful.</span>
              </div>
            ) : null}

            <div className="lesson-workspace">
              <div className="lesson-file-tabs" role="tablist" aria-label="Lesson files">
                {files.map((file) => <button className="lesson-file-tab" data-active={activeFile?.path === file.path || undefined} type="button" role="tab" aria-selected={activeFile?.path === file.path} onClick={() => setActiveFilePath(file.path)} key={file.path}>{file.path}</button>)}
              </div>
              {activeFile ? <MonacoEditor height="420px" language="python" theme="vs-dark" path={activeFile.path} value={activeFile.content} onChange={(content) => updateFile(activeFile.path, content ?? "")} options={{ minimap: { enabled: false }, fontSize: 14, tabSize: 4, automaticLayout: true, scrollBeyondLastLine: false }} /> : null}
            </div>
            <div className="lesson-actions"><button className="button" type="button" onClick={handleRun} disabled={running}>{running ? "Running checks…" : "Run checks"}</button></div>
            {runResult ? <pre className={`lesson-run-output ${runResult.passed ? "passed" : "failed"}`}>{runResult.output}</pre> : null}
          </div>
        ) : (
          <div><p className="muted">{concept.lesson?.status === "failed" ? "This lab could not be built." : "This lab is still being built."}</p></div>
        )
      ) : null}
    </div>
  );
}
