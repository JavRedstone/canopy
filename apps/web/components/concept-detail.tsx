"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { ConceptDetailResponse, CourseSummary, LessonRunResult, LessonWorkspaceFile, QuizItemPreview, ScriptRunResult, WorkedExamplePreview, getConceptDetail, getCourse, regenerateLesson, runLesson, runLessonScript } from "@/lib/api";
import { useFullBleed } from "@/components/app-shell";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { Icon } from "@/components/icon";
import { MarkdownText } from "@/components/markdown-text";
import { PageShell } from "@/components/page-shell";
import { QuizQuestion, QuizSection } from "@/components/quiz";
import { SettingsMenu } from "@/components/settings-menu";
import { conceptKindIcon, conceptKindLabel } from "@/lib/concept-kind";
import { createClient } from "@/lib/supabase/client";
import { parsePytestCases } from "@/lib/pytest-output";
import { useStallDetector } from "@/lib/use-stall-detector";
import { labTheme } from "@/lib/theme";
import type { ReactNode } from "react";
import { ThemeProvider } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Avatar from "@mui/material/Avatar";
import Divider from "@mui/material/Divider";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import Button from "@mui/material/Button";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import Badge from "@mui/material/Badge";
import Collapse from "@mui/material/Collapse";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogActions from "@mui/material/DialogActions";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });
const stallThresholdMs = 45_000;
const monoFont = "ui-monospace, SFMono-Regular, Menlo, monospace";
const editorOptionsBase = { minimap: { enabled: false }, fontSize: 12, tabSize: 4, scrollBeyondLastLine: false, scrollbar: { alwaysConsumeMouseWheel: false, verticalScrollbarSize: 10, horizontalScrollbarSize: 10 } };

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
    <Alert severity="info" variant="outlined" icon={false} sx={{ display: "grid", gap: 0.75 }}>
      <Typography sx={{ fontWeight: 700 }}>{example.title}</Typography>
      <MarkdownText citations={citations}>{example.body_markdown}</MarkdownText>
    </Alert>
  );
}

function WorkedExamples({ examples, citations }: { examples?: WorkedExamplePreview[]; citations?: string[] }) {
  if (!examples?.length) return null;
  return (
    <Stack sx={{ gap: 1.5 }}>
      <Divider textAlign="left"><Typography variant="overline" color="text.secondary">Worked examples</Typography></Divider>
      {examples.map((example) => (
        <WorkedExampleCard example={example} citations={citations} key={example.title} />
      ))}
    </Stack>
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
    if (text.trim()) blocks.push(<MarkdownText citations={citations} key={`text-${blocks.length}`}>{text}</MarkdownText>);
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
        <QuizQuestion courseId={courseId} slug={slug} item={quizItems[index]} index={placedQuiz.size - 1} maxAttempts={quizMaxAttempts} key={`quiz-${index}`} />
      );
    } else {
      flush();
    }
  }
  flush();
  const leftoverExamples = examples.filter((_, index) => !placedExamples.has(index));
  return (
    <Stack sx={{ gap: 1.5 }}>
      {blocks}
      <WorkedExamples examples={leftoverExamples} citations={citations} />
    </Stack>
  );
}

function defaultScratchScript(starterFiles: LessonWorkspaceFile[]): string {
  const moduleName = starterFiles[0]?.path.replace(/\.py$/, "") ?? "solution";
  return `# Import your solution and try anything - print() shows up below when you run it.\nfrom ${moduleName} import *\n`;
}

function BuildingBanner({ title, detail }: { title: string; detail: string }) {
  return (
    <Alert severity="info" icon={false}>
      <Stack direction="row" sx={{ alignItems: "center", gap: 1.5 }}>
        <CircularProgress size={22} />
        <Box>
          <Typography sx={{ fontWeight: 600 }}>{title}</Typography>
          <Typography variant="body2" color="text.secondary">{detail}</Typography>
        </Box>
      </Stack>
    </Alert>
  );
}

function TabDot({ ok }: { ok: boolean }) {
  return <Box component="span" sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: ok ? "success.main" : "error.main", display: "inline-block" }} />;
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
  const [solutionConfirmOpen, setSolutionConfirmOpen] = useState(false);
  const [consoleTab, setConsoleTab] = useState<"testcase" | "console" | "tests">("testcase");
  const [fullOutputOpen, setFullOutputOpen] = useState(false);

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

  // Unlocking the solution loads it straight into the live workspace editor -- in place
  // of whatever the learner had written -- so it can be run/submitted exactly like their
  // own work, rather than sitting inert as a read-only preview.
  function handleRevealSolution() {
    const solutionFiles = concept?.lesson?.solution_files ?? [];
    setFiles(solutionFiles.map((file) => ({ ...file })));
    setActiveFilePath(solutionFiles[0]?.path);
    setRunResult(undefined);
    setScriptResult(undefined);
    setConsoleTab("testcase");
    setSolutionRevealed(true);
    setSolutionConfirmOpen(false);
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

  if (state === "loading") {
    return (
      <PageShell>
        <Stack direction="row" sx={{ alignItems: "center", gap: 1.5, color: "text.secondary" }}>
          <CircularProgress size={18} /> <Typography>Loading…</Typography>
        </Stack>
      </PageShell>
    );
  }
  if (state === "error") return <PageShell><Alert severity="error">{errorMessage ?? "We could not load this concept."}</Alert></PageShell>;
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

  const conceptHeaderBadge = (
    <Avatar variant="rounded" sx={{ width: 32, height: 32, bgcolor: "action.hover", color: "text.primary", "& .material-symbol": { fontSize: 17, opacity: 0.75 } }}>
      <Icon name={conceptKindIcon(concept.kind)} />
    </Avatar>
  );

  const lessonSettingsMenu = (
    <SettingsMenu actions={[{ label: regenerating ? "Regenerating…" : "Regenerate lesson", icon: "refresh", onClick: handleRegenerateLesson, disabled: regenerating }]} label="Lesson settings" />
  );

  if (concept.kind !== "coding") {
    return (
      <PageShell>
        {breadcrumbs}
        <Stack direction="row" sx={{ alignItems: "flex-start", justifyContent: "space-between", gap: 3, mb: 4 }}>
          <Stack direction="row" sx={{ alignItems: "center", gap: 1.75 }}>
            {conceptHeaderBadge}
            <Box>
              <Typography variant="overline" color="text.secondary">{conceptKindLabel(concept.kind)}</Typography>
              <Typography variant="h4" sx={{ letterSpacing: "-0.02em", my: 0.25 }}>{concept.title}</Typography>
            </Box>
          </Stack>
          {lessonSettingsMenu}
        </Stack>

        <Stack sx={{ gap: 2 }}>
          <MarkdownText citations={concept.citations}>{concept.summary_markdown}</MarkdownText>
          {errorMessage ? <Alert severity="error">{errorMessage}</Alert> : null}

          {isBuildPending ? (
            <BuildingBanner
              title={generationStatus === "building" ? "Regenerating this lesson…" : "Lesson regeneration is queued…"}
              detail="This page refreshes automatically when the worker finishes."
            />
          ) : null}

          {generationStatus === "failed" ? <Alert severity="error">Lesson generation failed. Use Regenerate lesson to retry.</Alert> : null}

          {!isBuildPending && concept.lesson?.status === "built" && concept.lesson.explanation_markdown ? (
            <Stack sx={{ gap: 2 }}>
              <Divider textAlign="left"><Typography variant="overline" color="text.secondary">Lesson</Typography></Divider>
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
            </Stack>
          ) : null}
        </Stack>
      </PageShell>
    );
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", gap: 2, p: "12px 24px", borderBottom: 1, borderColor: "divider", flexShrink: 0 }}>
        <Stack sx={{ gap: 0.5, minWidth: 0 }}>
          {breadcrumbs}
          <Stack direction="row" sx={{ alignItems: "center", gap: 1.25 }}>
            {conceptHeaderBadge}
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="overline" color="text.secondary">{conceptKindLabel(concept.kind)}</Typography>
              <Typography variant="h6" sx={{ letterSpacing: "-0.01em", mt: "2px" }} noWrap>{concept.title}</Typography>
            </Box>
          </Stack>
        </Stack>
        {lessonSettingsMenu}
      </Stack>

      <Dialog open={solutionConfirmOpen} onClose={() => setSolutionConfirmOpen(false)}>
        <DialogTitle>Unlock the reference solution?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This replaces whatever you&apos;ve written in the editor with the reference solution, which you can then run or submit.
            Your current code in the editor will be lost.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button variant="text" onClick={() => setSolutionConfirmOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleRevealSolution}>Unlock solution</Button>
        </DialogActions>
      </Dialog>

      {errorMessage ? <Alert severity="error" sx={{ mx: 3, mt: 1.5 }}>{errorMessage}</Alert> : null}

      {concept.lesson && concept.lesson.status === "built" ? (
        <Box sx={{ flex: 1, minHeight: 0, display: "flex" }}>
          <Box sx={{ width: 420, flexShrink: 0, overflowY: "auto", p: "16px 24px 40px", borderRight: 1, borderColor: "divider", display: "grid", gap: 2, alignContent: "start" }}>
            <Tabs value={instructionsTab} onChange={(_event, value) => setInstructionsTab(value)} sx={{ minHeight: 36, mx: -3, px: 3, borderBottom: 1, borderColor: "divider" }}>
              <Tab value="lesson" label="Lesson" sx={{ minHeight: 36, py: 1, textTransform: "none" }} />
              {concept.lesson.solution_files.length > 0 ? (
                <Tab
                  value="solution"
                  label={
                    solutionRevealed ? (
                      "Solution"
                    ) : (
                      <Stack direction="row" sx={{ alignItems: "center", gap: 0.5 }}><Icon name="lock" /> Solution</Stack>
                    )
                  }
                  sx={{ minHeight: 36, py: 1, textTransform: "none" }}
                />
              ) : null}
            </Tabs>

            {instructionsTab === "lesson" ? (
              <Stack sx={{ gap: 2 }}>
                <MarkdownText citations={concept.citations}>{concept.summary_markdown}</MarkdownText>

                {concept.lesson.explanation_markdown ? (
                  <Stack sx={{ gap: 1.5 }}>
                    <Divider textAlign="left"><Typography variant="overline" color="text.secondary">Lesson</Typography></Divider>
                    <LessonBody
                      courseId={courseId}
                      slug={slug}
                      markdown={concept.lesson.explanation_markdown}
                      citations={concept.citations}
                      examples={concept.lesson.worked_examples ?? []}
                      quizItems={concept.lesson.quiz_items ?? []}
                      quizMaxAttempts={concept.lesson.quiz_max_attempts}
                    />
                  </Stack>
                ) : (
                  <WorkedExamples examples={concept.lesson.worked_examples} citations={concept.citations} />
                )}

                {concept.lesson.hints.length > 0 ? (
                  <Alert severity="info" variant="outlined" icon={false} sx={{ display: "grid", gap: 0.75 }}>
                    <Typography sx={{ fontWeight: 700 }}>Hints</Typography>
                    <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                      {concept.lesson.hints.map((hint, index) => (
                        <Typography component="li" variant="body2" key={index}>{hint}</Typography>
                      ))}
                    </Box>
                  </Alert>
                ) : null}

                <QuizSection
                  courseId={courseId}
                  slug={slug}
                  items={(concept.lesson.quiz_items ?? []).filter(
                    (_, index) => !markerReferencedQuizIndexes(concept.lesson?.explanation_markdown ?? "").has(index)
                  )}
                  maxAttempts={concept.lesson.quiz_max_attempts}
                />
              </Stack>
            ) : !solutionRevealed ? (
              <Stack sx={{ gap: 1.5, py: 3, alignItems: "flex-start" }}>
                <Icon name="lock" />
                <Typography color="text.secondary">Seeing the reference solution before you&apos;ve solved it yourself will spoil the exercise.</Typography>
                <Button variant="outlined" onClick={() => setSolutionConfirmOpen(true)}>Show solution</Button>
              </Stack>
            ) : (
              <Stack sx={{ gap: 2 }}>
                <Alert severity="success" icon={<Icon name="lock_open" />}>
                  The reference solution is now loaded in your editor on the right -- run or submit it like your own work.
                </Alert>
                {concept.lesson.explanation_markdown ? (
                  <LessonBody
                    courseId={courseId}
                    slug={slug}
                    markdown={concept.lesson.explanation_markdown}
                    citations={concept.citations}
                    examples={concept.lesson.worked_examples ?? []}
                    quizItems={concept.lesson.quiz_items ?? []}
                    quizMaxAttempts={concept.lesson.quiz_max_attempts}
                  />
                ) : (
                  <WorkedExamples examples={concept.lesson.worked_examples} citations={concept.citations} />
                )}
              </Stack>
            )}
          </Box>

          <ThemeProvider theme={labTheme}>
            <Box
              sx={{
                flex: 1,
                minWidth: 0,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                bgcolor: "background.default",
                color: "text.primary",
                scrollbarColor: "#4a4a4a transparent",
                "& *::-webkit-scrollbar-thumb": { backgroundColor: "#4a4a4a" },
                "& *::-webkit-scrollbar-thumb:hover": { backgroundColor: "#666" }
              }}
            >
              <Stack direction="row" sx={{ alignItems: "center", bgcolor: "background.paper", borderBottom: 1, borderColor: "divider" }}>
                <Tabs
                  value={activeFile?.path ?? false}
                  onChange={(_event, value) => setActiveFilePath(value)}
                  variant="scrollable"
                  scrollButtons="auto"
                  sx={{ minHeight: 38, flex: 1, minWidth: 0 }}
                >
                  {files.map((file) => (
                    <Tab
                      key={file.path}
                      value={file.path}
                      label={<Stack direction="row" sx={{ alignItems: "center", gap: 0.75 }}><Icon name="code" /> {file.path}</Stack>}
                      sx={{ minHeight: 38, textTransform: "none", fontFamily: monoFont, fontSize: "0.78rem" }}
                    />
                  ))}
                  {publicTestFiles.map((file) => (
                    <Tab
                      key={file.path}
                      value={file.path}
                      label={<Stack direction="row" sx={{ alignItems: "center", gap: 0.75 }}><Icon name="lock" /> {file.path}</Stack>}
                      sx={{ minHeight: 38, textTransform: "none", fontStyle: "italic", color: "warning.main", fontFamily: monoFont, fontSize: "0.78rem" }}
                    />
                  ))}
                </Tabs>
                <Stack direction="row" sx={{ gap: 1, px: 1.25, borderLeft: 1, borderColor: "divider", flexShrink: 0 }}>
                  <Button size="small" variant="outlined" color="success" startIcon={<Icon name="play_arrow" />} onClick={handleRunScript} loading={runningScript} sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700 }}>
                    Run
                  </Button>
                  <Button size="small" variant="contained" color="success" startIcon={<Icon name="play_arrow" />} onClick={handleRun} loading={running} sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700 }}>
                    Submit
                  </Button>
                </Stack>
              </Stack>
              {activeFileIsReadOnly ? (
                <Typography variant="body2" color="text.secondary" sx={{ px: 2, pt: 1 }}>
                  This is one of the checks your solution is graded against (read-only, but always included when you Submit).
                </Typography>
              ) : null}
              <Box sx={{ flex: 1, minHeight: 0 }}>
                {activeFile ? (
                  <MonacoEditor
                    height="100%"
                    language="python"
                    theme="vs-dark"
                    path={activeFile.path}
                    value={activeFile.content}
                    onChange={(content) => { if (!activeFileIsReadOnly) updateFile(activeFile.path, content ?? ""); }}
                    options={{ ...editorOptionsBase, automaticLayout: true, readOnly: activeFileIsReadOnly }}
                  />
                ) : null}
              </Box>

              <Box sx={{ flexShrink: 0, height: 260, display: "flex", flexDirection: "column", borderTop: 1, borderColor: "divider", bgcolor: "background.paper" }}>
                <Tabs value={consoleTab} onChange={(_event, value) => setConsoleTab(value)} sx={{ minHeight: 34, px: 1, pt: 1 }}>
                  <Tab
                    value="testcase"
                    label={<Stack direction="row" sx={{ alignItems: "center", gap: 0.75 }}><Icon name="edit_note" /> Testcase</Stack>}
                    sx={{ minHeight: 34, textTransform: "none" }}
                  />
                  <Tab
                    value="console"
                    label={
                      <Stack direction="row" sx={{ alignItems: "center", gap: 0.75 }}>
                        <Icon name="terminal" /> Console
                        {scriptResult ? <TabDot ok={scriptResult.exit_code === 0 && !scriptResult.timed_out} /> : null}
                      </Stack>
                    }
                    sx={{ minHeight: 34, textTransform: "none" }}
                  />
                  <Tab
                    value="tests"
                    label={
                      <Stack direction="row" sx={{ alignItems: "center", gap: 0.75 }}>
                        <Icon name="fact_check" /> Test Result
                        {runResult ? <TabDot ok={runResult.passed} /> : null}
                      </Stack>
                    }
                    sx={{ minHeight: 34, textTransform: "none" }}
                  />
                </Tabs>
                <Box sx={{ flex: 1, minHeight: 0, overflowY: "auto", bgcolor: "background.default", p: "12px 14px", display: "grid", gap: 1.25, alignContent: "start" }}>
                  {consoleTab === "testcase" ? (
                    <>
                      <Typography variant="body2" color="text.secondary">
                        Edit this script to call your code with whatever input you want, then hit Run to see what it prints. Never affects grading.
                      </Typography>
                      <MonacoEditor
                        height="150px"
                        language="python"
                        theme="vs-dark"
                        path="scratch.py"
                        value={scratchCode}
                        onChange={(content) => setScratchCode(content ?? "")}
                        options={{ ...editorOptionsBase, automaticLayout: true }}
                      />
                    </>
                  ) : consoleTab === "console" ? (
                    scriptResult ? (
                      <Box
                        component="pre"
                        sx={{
                          m: 0, p: 1.75, borderRadius: 1, overflowX: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word",
                          fontSize: "0.82rem", bgcolor: "#131313", color: "#ddd",
                          borderLeft: 3, borderColor: scriptResult.exit_code === 0 && !scriptResult.timed_out ? "success.main" : "error.main"
                        }}
                      >
                        {scriptResult.output || "(no output)"}
                        {scriptResult.timed_out ? "\n\n[timed out]" : scriptResult.exit_code !== 0 ? `\n\n[exited with code ${scriptResult.exit_code}]` : ""}
                      </Box>
                    ) : (
                      <Typography variant="body2" color="text.secondary">Edit your script on the Testcase tab, then hit Run above to see its output here.</Typography>
                    )
                  ) : runResult ? (
                    <>
                      <Typography variant="body2" color="text.secondary">
                        Submit swaps in the full test suite, including hidden checks you can&apos;t see, to validate your solution.
                      </Typography>
                      {(() => {
                        const cases = parsePytestCases(runResult.output);
                        return cases.length > 0 ? (
                          <Stack component="ul" sx={{ listStyle: "none", m: 0, p: 0, gap: "2px" }}>
                            {cases.map((testCase, index) => (
                              <Stack
                                component="li"
                                direction="row"
                                key={index}
                                sx={{
                                  alignItems: "center", gap: 1, px: 1, py: 0.75, borderRadius: 1, fontSize: "0.85rem",
                                  color: testCase.status === "passed" ? "success.light" : testCase.status === "skipped" ? "text.secondary" : "error.light"
                                }}
                              >
                                <Icon name={testCase.status === "passed" ? "check_circle" : testCase.status === "skipped" ? "remove_circle" : "cancel"} />
                                <Typography variant="body2" sx={{ color: "inherit" }}>{testCase.name}</Typography>
                              </Stack>
                            ))}
                          </Stack>
                        ) : null;
                      })()}
                      <Box>
                        <Button
                          size="small"
                          variant="text"
                          color="inherit"
                          onClick={() => setFullOutputOpen((current) => !current)}
                          sx={{ textTransform: "none", color: "text.secondary", px: 0 }}
                        >
                          {fullOutputOpen ? "Hide full output" : "Full output"}
                        </Button>
                        <Collapse in={fullOutputOpen}>
                          <Box
                            component="pre"
                            sx={{
                              mt: 1, mb: 0, p: 1.75, borderRadius: 1, overflowX: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word",
                              fontSize: "0.82rem", bgcolor: "#131313", color: "#ddd",
                              borderLeft: 3, borderColor: runResult.passed ? "success.main" : "error.main"
                            }}
                          >
                            {runResult.output}
                          </Box>
                        </Collapse>
                      </Box>
                    </>
                  ) : (
                    <Typography variant="body2" color="text.secondary">Hit Submit above to see check results here.</Typography>
                  )}
                </Box>
              </Box>
            </Box>
          </ThemeProvider>
        </Box>
      ) : concept.lesson?.status === "failed" ? (
        <Box sx={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", p: "40px 24px" }}>
          <Stack sx={{ gap: 1.25, alignItems: "flex-start" }}>
            <Alert severity="error">This lab could not be built.</Alert>
            <Button variant="outlined" onClick={handleRegenerateLesson} disabled={regenerating}>
              {regenerating ? "Regenerating…" : "Try again"}
            </Button>
          </Stack>
        </Box>
      ) : (
        <Box sx={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", p: "40px 24px" }}>
          <Stack sx={{ gap: 1.5, width: "min(480px, 100%)" }}>
            <BuildingBanner
              title={lessonStatus === "building" ? "Building this lab…" : "Queued to build…"}
              detail="This page updates automatically as soon as it's ready."
            />
            {stalled ? (
              <Alert severity="warning" action={<Button color="inherit" size="small" onClick={handleRegenerateLesson} disabled={regenerating}>{regenerating ? "Resuming…" : "Resume build"}</Button>}>
                This is taking longer than expected; the build may have stalled.
              </Alert>
            ) : null}
          </Stack>
        </Box>
      )}
    </Box>
  );
}
