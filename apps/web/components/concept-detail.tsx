"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { ConceptDetailResponse, ConceptMastery, CourseMapResponse, CourseMasteryResponse, CourseSummary, LessonRunResult, LessonWorkspaceFile, QuizItemPreview, ScriptRunResult, WorkedExamplePreview, askLessonHelper, clearDemoProgress, getConceptDetail, getCourse, getCourseMap, getCourseMastery, getDemoAutoCompleteStatus, regenerateLesson, runLesson, runLessonScript, startDemoAutoComplete, submitLesson } from "@/lib/api";
import { useFullBleed } from "@/components/app-shell";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { CitationExcerptDialog } from "@/components/citation-excerpt-dialog";
import { Icon } from "@/components/icon";
import { MarkdownText } from "@/components/markdown-text";
import { PageShell } from "@/components/page-shell";
import { QuizQuestion, QuizSection } from "@/components/quiz";
import { MasteryCard } from "@/components/mastery-meter";
import { PrerequisiteReview } from "@/components/prerequisite-review";
import { PrerequisiteNudge } from "@/components/prerequisite-nudge";
import { SettingsMenu } from "@/components/settings-menu";
import { ConfettiBurst } from "@/components/confetti-burst";
import { conceptKindColor, conceptKindIcon, conceptKindLabel } from "@/lib/concept-kind";
import { createClient } from "@/lib/supabase/client";
import { parsePytestCases } from "@/lib/pytest-output";
import { useStallDetector } from "@/lib/use-stall-detector";
import { labTheme } from "@/lib/theme";
import type { ReactNode } from "react";
import { ThemeProvider, alpha } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Avatar from "@mui/material/Avatar";
import Divider from "@mui/material/Divider";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import Collapse from "@mui/material/Collapse";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogActions from "@mui/material/DialogActions";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import TextField from "@mui/material/TextField";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });
const stallThresholdMs = 45_000;
const monoFont = "ui-monospace, SFMono-Regular, Menlo, monospace";
const editorOptionsBase = { minimap: { enabled: false }, fontSize: 12, tabSize: 4, scrollBeyondLastLine: false, scrollbar: { alwaysConsumeMouseWheel: false, verticalScrollbarSize: 10, horizontalScrollbarSize: 10 } };

// The bundle doesn't carry an explicit language field to the frontend -- the file
// extension already says it, and it's the one thing Monaco actually needs for highlighting.
function monacoLanguageForPath(path: string): string {
  if (path.endsWith(".cpp") || path.endsWith(".h") || path.endsWith(".hpp")) return "cpp";
  return "python";
}

// A marker the lesson generator emits to place a worked example or quiz item inside the
// prose, e.g. "{{example:1}}" or "{{quiz:2}}" (1-based indexes). Meant to sit alone on its
// own line, but matched anywhere in a line since the model occasionally tacks one onto the
// end of a sentence instead -- the rest of that line still renders as ordinary prose.
const LESSON_MARKER = /\{\{\s*(example|quiz)\s*:\s*(\d+)\s*\}\}/;

/** Map rendered prose back to its Markdown positions so a browser text selection can
 * replace the right source span even when it crosses whitespace or inline emphasis. */
function replaceVisiblePassage(markdown: string, selected: string, replacement: string): string | null {
  if (markdown.includes(selected)) return markdown.replace(selected, replacement);
  const visible: string[] = [];
  const sourceIndexes: number[] = [];
  let previousWasSpace = false;
  for (let index = 0; index < markdown.length; index += 1) {
    const character = markdown[index];
    if (character === "*" || character === "`") continue;
    if (/\s/.test(character)) {
      if (!previousWasSpace) {
        visible.push(" ");
        sourceIndexes.push(index);
        previousWasSpace = true;
      }
      continue;
    }
    visible.push(character);
    sourceIndexes.push(index);
    previousWasSpace = false;
  }
  const selectedVisible = selected.replace(/[\*`]/g, "").replace(/\s+/g, " ").trim();
  const sourceVisible = visible.join("");
  const start = sourceVisible.indexOf(selectedVisible);
  if (start < 0) return null;
  const end = start + selectedVisible.length - 1;
  return markdown.slice(0, sourceIndexes[start]) + replacement + markdown.slice(sourceIndexes[end] + 1);
}

function markerReferencedQuizIndexes(markdown: string): Set<number> {
  const referenced = new Set<number>();
  for (const line of markdown.split("\n")) {
    const match = line.match(LESSON_MARKER);
    if (match && match[1] === "quiz") referenced.add(Number(match[2]) - 1);
  }
  return referenced;
}

function WorkedExampleCard({ example, citations, onCitationClick }: { example: WorkedExamplePreview; citations?: string[]; onCitationClick?: (citationId: string) => void }) {
  return (
    <Alert severity="info" variant="outlined" icon={false} sx={{ display: "grid", gap: 0.75 }}>
      <Typography sx={{ fontWeight: 700 }}>{example.title}</Typography>
      <MarkdownText citations={citations} onCitationClick={onCitationClick}>{example.body_markdown}</MarkdownText>
    </Alert>
  );
}

function WorkedExamples({ examples, citations, onCitationClick }: { examples?: WorkedExamplePreview[]; citations?: string[]; onCitationClick?: (citationId: string) => void }) {
  if (!examples?.length) return null;
  return (
    <Stack sx={{ gap: 1.5 }}>
      <Divider textAlign="left"><Typography variant="overline" color="text.secondary">Worked examples</Typography></Divider>
      {examples.map((example) => (
        <WorkedExampleCard example={example} citations={citations} onCitationClick={onCitationClick} key={example.title} />
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
  onQuizAnswered,
  highlightText,
  highlightParagraphId,
  highlightOccurrence,
  highlightFlash,
  paragraphGroup,
  onCitationClick,
  onAskHelperForQuiz,
}: {
  courseId: string;
  slug: string;
  markdown: string;
  citations?: string[];
  examples: WorkedExamplePreview[];
  quizItems: QuizItemPreview[];
  quizMaxAttempts: number;
  onQuizAnswered?: () => void;
  highlightText?: string;
  highlightParagraphId?: string;
  highlightOccurrence?: number;
  highlightFlash?: boolean;
  paragraphGroup?: string;
  onCitationClick?: (citationId: string) => void;
  onAskHelperForQuiz?: (item: QuizItemPreview) => void;
}) {
  const blocks: ReactNode[] = [];
  const placedExamples = new Set<number>();
  const placedQuiz = new Set<number>();
  let buffer: string[] = [];
  let insideCodeFence = false;
  const flush = () => {
    const text = buffer.join("\n");
    if (text.trim()) blocks.push(<MarkdownText citations={citations} highlightText={highlightText} highlightParagraphId={highlightParagraphId} highlightOccurrence={highlightOccurrence} highlightFlash={highlightFlash} paragraphGroup={`${paragraphGroup ?? "lesson"}-${blocks.length}`} onCitationClick={onCitationClick} key={`text-${blocks.length}`}>{text}</MarkdownText>);
    buffer = [];
  };
  for (const rawLine of markdown.split("\n")) {
    if (rawLine.trimStart().startsWith("```")) insideCodeFence = !insideCodeFence;
    if (insideCodeFence) {
      buffer.push(rawLine);
      continue;
    }
    let remainder = rawLine;
    let sawMarker = false;
    let match: RegExpMatchArray | null;
    while ((match = remainder.match(LESSON_MARKER))) {
      sawMarker = true;
      const before = remainder.slice(0, match.index).trim();
      if (before) buffer.push(before);
      const index = Number(match[2]) - 1;
      if (match[1] === "example" && examples[index] && !placedExamples.has(index)) {
        flush();
        placedExamples.add(index);
        blocks.push(<WorkedExampleCard example={examples[index]} citations={citations} onCitationClick={onCitationClick} key={`example-${index}`} />);
      } else if (match[1] === "quiz" && quizItems[index] && !placedQuiz.has(index)) {
        flush();
        placedQuiz.add(index);
        blocks.push(
          <QuizQuestion courseId={courseId} slug={slug} item={quizItems[index]} index={placedQuiz.size - 1} maxAttempts={quizMaxAttempts} onAnswered={onQuizAnswered} onAskHelper={onAskHelperForQuiz} key={`quiz-${index}`} />
        );
      } else {
        flush();
      }
      remainder = remainder.slice((match.index ?? 0) + match[0].length);
    }
    buffer.push(sawMarker ? remainder.trim() : rawLine);
  }
  flush();
  const leftoverExamples = examples.filter((_, index) => !placedExamples.has(index));
  return (
    <Stack sx={{ gap: 1.5 }}>
      {blocks}
      <WorkedExamples examples={leftoverExamples} citations={citations} onCitationClick={onCitationClick} />
    </Stack>
  );
}

function defaultScratchScript(starterFiles: LessonWorkspaceFile[]): string {
  const moduleName = starterFiles[0]?.path.replace(/\.py$/, "") ?? "solution";
  return `# Import your solution and try anything - print() shows up below when you run it.\nfrom ${moduleName} import *\n`;
}

// "classification_workflow.py" -> "classification_workflow_solution.py", so the revealed
// solution lands in its own tab next to the learner's file rather than colliding with it.
function solutionFilePath(path: string): string {
  const dotIndex = path.lastIndexOf(".");
  return dotIndex === -1 ? `${path}_solution` : `${path.slice(0, dotIndex)}_solution${path.slice(dotIndex)}`;
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

function CourseOutlineSidebar({ courseId, map, activeSlug, collapsed, onToggle }: { courseId: string; map?: CourseMapResponse; activeSlug: string; collapsed: boolean; onToggle: () => void }) {
  return (
    <Box component="aside" sx={{ display: { xs: "none", md: "block" }, position: "fixed", top: 64, bottom: 0, left: 0, zIndex: 2, width: collapsed ? 56 : 280, overflowX: "hidden", overflowY: "auto", borderRight: 1, borderColor: "divider", bgcolor: "background.paper", p: 1.25, transition: (theme) => theme.transitions.create("width", { duration: 180 }) }}>
      <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", px: collapsed ? 0 : 1, mb: 0.75 }}>
        {!collapsed ? <Typography variant="overline" color="text.secondary">Course outline</Typography> : null}
        <IconButton size="small" onClick={onToggle} aria-label={collapsed ? "Expand course outline" : "Collapse course outline"}>
          <Icon name={collapsed ? "chevron_right" : "chevron_left"} />
        </IconButton>
      </Stack>
      {!collapsed && !map ? <Stack direction="row" sx={{ alignItems: "center", gap: 1, px: 1, color: "text.secondary" }}><CircularProgress size={14} /><Typography variant="body2">Loading outline…</Typography></Stack> : null}
      {!collapsed && map ? <List disablePadding sx={{ display: "grid", gap: 1 }}>
        {map.modules.map((module) => (
          <Box key={module.position}>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", px: 1, pb: 0.5 }}>
              {module.position}. {module.title}
            </Typography>
            {module.concepts.map((item) => (
              <ListItemButton
                key={item.slug}
                component={Link}
                href={`/courses/${courseId}/concepts/${item.slug}`}
                selected={item.slug === activeSlug}
                sx={{ borderRadius: 1, py: 0.75, px: 1, alignItems: "flex-start" }}
              >
                <ListItemIcon sx={{ minWidth: 28, mt: 0.15 }}>
                  <Icon name={conceptKindIcon(item.kind)} />
                </ListItemIcon>
                <ListItemText primary={item.title} secondary={conceptKindLabel(item.kind)} slotProps={{ primary: { sx: { fontSize: "0.82rem", lineHeight: 1.25 } }, secondary: { sx: { fontSize: "0.72rem" } } }} />
                {item.completed ? (
                  <Box component="span" sx={{ mt: 0.15, color: "success.main", display: "inline-flex", "& .material-symbol": { fontSize: 16 } }}>
                    <Icon name="check_circle" />
                  </Box>
                ) : null}
              </ListItemButton>
            ))}
          </Box>
        ))}
      </List> : null}
    </Box>
  );
}

/** A small floating "Ask" pill that appears next to a text selection, so the learning
 *  helper is discoverable without spotting the collapsed icon rail on the page edge. */
function SelectionAskBubble({ rect, onAsk }: { rect: { top: number; left: number }; onAsk: () => void }) {
  return (
    <Box sx={{ display: { xs: "none", lg: "block" }, position: "fixed", top: rect.top, left: rect.left, transform: "translateX(-50%)", zIndex: 4 }}>
      <Button variant="contained" size="small" startIcon={<Icon name="auto_awesome" />} onClick={onAsk} sx={{ boxShadow: 3 }}>
        Ask
      </Button>
    </Box>
  );
}

function LessonNavigation({ courseId, map, activeSlug }: { courseId: string; map?: CourseMapResponse; activeSlug: string }) {
  const lessons = map?.modules.flatMap((module) => module.concepts) ?? [];
  const index = lessons.findIndex((item) => item.slug === activeSlug);
  if (index < 0) return null;
  const previous = lessons[index - 1];
  const next = lessons[index + 1];
  return (
    <Stack direction="row" sx={{ justifyContent: "space-between", gap: 1, pt: 1 }}>
      {previous ? <Button component={Link} href={`/courses/${courseId}/concepts/${previous.slug}`} variant="outlined" startIcon={<Icon name="arrow_back" />}>Previous</Button> : <Box />}
      {next ? <Button component={Link} href={`/courses/${courseId}/concepts/${next.slug}`} variant="contained" endIcon={<Icon name="arrow_forward" />}>Next lesson</Button> : <Button component={Link} href={`/courses/${courseId}`} variant="contained" endIcon={<Icon name="school" />}>Back to course</Button>}
    </Stack>
  );
}

function LessonComplete({ courseId, map, slug, title }: { courseId: string; map?: CourseMapResponse; slug: string; title: string }) {
  return (
    <Alert severity="success" icon={<Icon name="celebration" />} sx={{ position: "relative", overflow: "hidden" }}>
      <ConfettiBurst />
      <Typography sx={{ fontWeight: 700 }}>{title} complete!</Typography>
      <Typography variant="body2">Nice work! You&apos;re ready for the next activity.</Typography>
      <LessonNavigation courseId={courseId} map={map} activeSlug={slug} />
    </Alert>
  );
}

function LearningHelperSidebar({
  courseId,
  slug,
  selectedText,
  selectedParagraph,
  focusedQuizItem,
  workspaceFiles,
  open,
  onToggle,
  onClearSelection,
  onApplyRevision,
}: {
  courseId: string;
  slug: string;
  selectedText: string;
  selectedParagraph?: { id: string; source: string; occurrence: number };
  focusedQuizItem?: QuizItemPreview;
  workspaceFiles?: LessonWorkspaceFile[];
  open: boolean;
  onToggle: () => void;
  onClearSelection: () => void;
  onApplyRevision: (replacement: string) => boolean;
}) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string>();
  const [replacement, setReplacement] = useState<string>();
  const [applied, setApplied] = useState(false);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string>();

  // Reset the previous answer whenever the lesson, focused passage, or focused quiz
  // question changes, without an effect: comparing against the previous key during render
  // (React's "adjusting state during render" pattern) avoids the extra render an effect
  // would cause.
  const resetKey = `${slug}::${selectedText}::${focusedQuizItem?.id ?? ""}`;
  const [lastResetKey, setLastResetKey] = useState(resetKey);
  if (resetKey !== lastResetKey) {
    setLastResetKey(resetKey);
    setAnswer(undefined);
    setReplacement(undefined);
    setApplied(false);
    setError(undefined);
  }

  async function ask(questionOverride?: string, requestRevision = false) {
    const text = (questionOverride ?? question).trim();
    if (!text) return;
    setQuestion(text);
    setAsking(true);
    setError(undefined);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const revisionContext = requestRevision && selectedParagraph ? selectedParagraph.source : selectedText;
      const response = await askLessonHelper(courseId, slug, text, revisionContext || undefined, data.session.access_token, requestRevision, {
        workspaceFiles,
        quizItemId: focusedQuizItem?.id,
      });
      setAnswer(response.answer_markdown);
      setReplacement(response.replacement_markdown ?? undefined);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to ask the learning helper.");
    } finally {
      setAsking(false);
    }
  }

  return (
    <Box component="aside" sx={{ display: { xs: "none", lg: "block" }, position: "fixed", top: 64, right: 0, bottom: 0, zIndex: 2, width: open ? 360 : 56, overflow: "hidden", borderLeft: 1, borderColor: "divider", bgcolor: "background.paper", transition: (theme) => theme.transitions.create("width", { duration: 180 }) }}>
      <Stack direction="row" sx={{ height: 52, alignItems: "center", justifyContent: open ? "space-between" : "center", px: open ? 1.5 : 0.5, borderBottom: 1, borderColor: "divider" }}>
        {open ? <Stack direction="row" sx={{ alignItems: "center", gap: 1 }}><Icon name="auto_awesome" /><Typography sx={{ fontWeight: 700 }}>Learning helper</Typography></Stack> : null}
        <IconButton size="small" onClick={onToggle} aria-label={open ? "Collapse learning helper" : "Open learning helper"}>
          <Icon name={open ? "chevron_right" : "auto_awesome"} />
        </IconButton>
      </Stack>
      {open ? (
        <Stack sx={{ height: "calc(100% - 52px)", p: 2, gap: 1.5, overflowY: "auto" }}>
          <Typography variant="body2" color="text.secondary">
            Ask about anything on this lesson, lab, or quiz question. The helper uses the whole page, and can focus
            on an optional passage or question -- it guides you toward the answer without giving it away.
          </Typography>
          {focusedQuizItem ? (
            <Box sx={{ p: 1.25, borderRadius: 1.5, bgcolor: "action.hover", borderLeft: 3, borderColor: "primary.main", position: "relative" }}>
              <IconButton size="small" onClick={onClearSelection} aria-label="Use the full lesson instead" sx={{ position: "absolute", top: 4, right: 4 }}>
                <Icon name="close" />
              </IconButton>
              <Typography variant="caption" color="text.secondary">Focused question</Typography>
              <Typography variant="body2" sx={{ mt: 0.4, pr: 3, whiteSpace: "pre-wrap", display: "-webkit-box", WebkitLineClamp: 6, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{focusedQuizItem.prompt_markdown}</Typography>
            </Box>
          ) : selectedText ? (
            <Box sx={{ p: 1.25, borderRadius: 1.5, bgcolor: "action.hover", borderLeft: 3, borderColor: "primary.main", position: "relative" }}>
              <IconButton size="small" onClick={onClearSelection} aria-label="Use the full lesson instead" sx={{ position: "absolute", top: 4, right: 4 }}>
                <Icon name="close" />
              </IconButton>
              <Typography variant="caption" color="text.secondary">Focused passage</Typography>
              <Typography variant="body2" sx={{ mt: 0.4, pr: 3, whiteSpace: "pre-wrap", display: "-webkit-box", WebkitLineClamp: 6, WebkitBoxOrient: "vertical", overflow: "hidden" }}>&ldquo;{selectedText}&rdquo;</Typography>
            </Box>
          ) : null}
          <Stack direction="row" sx={{ flexWrap: "wrap", gap: 0.75 }}>
            {focusedQuizItem ? (
              <Button size="small" variant="outlined" onClick={() => void ask("I'm not sure how to approach this question. Can you give me a hint, without telling me the answer?")}>Give me a hint</Button>
            ) : workspaceFiles?.length ? (
              <Button size="small" variant="outlined" onClick={() => void ask("I'm stuck on this exercise. Can you give me a hint based on my current code, without telling me the answer?")}>Give me a hint</Button>
            ) : (
              <>
                <Button size="small" variant="outlined" onClick={() => void ask("Explain this more simply.")}>Explain simply</Button>
                <Button size="small" variant="outlined" onClick={() => void ask("Why does this matter in practice?")}>Why it matters</Button>
              </>
            )}
          </Stack>
          <TextField
            label="Ask about this lesson"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            multiline
            minRows={3}
            placeholder="What does this mean?"
            slotProps={{ htmlInput: { maxLength: 1200 } }}
          />
          <Button variant="contained" startIcon={<Icon name="send" />} onClick={() => void ask()} disabled={!question.trim()} loading={asking}>Ask helper</Button>
          {error ? <Alert severity="error">{error}</Alert> : null}
          {answer ? <Box sx={{ pt: 0.5 }}><Divider sx={{ mb: 1.5 }} /><MarkdownText>{answer}</MarkdownText></Box> : null}
          {answer && selectedText && !replacement ? (
            <Button variant="outlined" color="success" startIcon={<Icon name="auto_fix_high" />} onClick={() => void ask(question || "Make this selected passage clearer.", true)} loading={asking}>
              Rewrite selected paragraph
            </Button>
          ) : null}
          {replacement && selectedText ? (
            <Stack sx={{ gap: 1 }}>
              <Divider />
              <Typography variant="subtitle2">Suggested clearer version</Typography>
              <Box sx={{ p: 1.25, borderRadius: 1.5, bgcolor: "action.hover" }}><MarkdownText>{replacement}</MarkdownText></Box>
              <Button variant={applied ? "outlined" : "contained"} color="success" startIcon={<Icon name={applied ? "check" : "auto_fix_high"} />} onClick={() => setApplied(onApplyRevision(replacement))} disabled={applied}>
                {applied ? "Applied to lesson" : "Apply to lesson"}
              </Button>
            </Stack>
          ) : null}
        </Stack>
      ) : null}
    </Box>
  );
}

export function ConceptDetail({ courseId, slug }: { courseId: string; slug: string }) {
  const [course, setCourse] = useState<CourseSummary>();
  const [concept, setConcept] = useState<ConceptDetailResponse>();
  const [courseMap, setCourseMap] = useState<CourseMapResponse>();
  const [outlineCollapsed, setOutlineCollapsed] = useState(false);
  const [codeCollapsed, setCodeCollapsed] = useState(false);
  const [helperOpen, setHelperOpen] = useState(false);
  const [selectedText, setSelectedText] = useState("");
  const [selectedRange, setSelectedRange] = useState<Range>();
  const [selectedParagraph, setSelectedParagraph] = useState<{ id: string; source: string; occurrence: number }>();
  const [focusedQuizItem, setFocusedQuizItem] = useState<QuizItemPreview>();
  const [bubbleRect, setBubbleRect] = useState<{ top: number; left: number }>();
  const [lessonUpdateNotice, setLessonUpdateNotice] = useState(false);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string>();
  const [files, setFiles] = useState<LessonWorkspaceFile[]>([]);
  const [testResult, setTestResult] = useState<LessonRunResult>();
  const [running, setRunning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [labComplete, setLabComplete] = useState(false);
  const [mastery, setMastery] = useState<CourseMasteryResponse>();
  const [celebrateNonce, setCelebrateNonce] = useState(0);
  const [assessmentComplete, setAssessmentComplete] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [demoFilling, setDemoFilling] = useState(false);
  const [demoClearing, setDemoClearing] = useState(false);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [activeFilePath, setActiveFilePath] = useState<string>();
  const [scratchCode, setScratchCode] = useState("");
  const [scriptResult, setScriptResult] = useState<ScriptRunResult>();
  const [runningScript, setRunningScript] = useState(false);
  const [instructionsTab, setInstructionsTab] = useState<"lesson" | "solution">("lesson");
  const [solutionRevealed, setSolutionRevealed] = useState(false);
  const [solutionConfirmOpen, setSolutionConfirmOpen] = useState(false);
  const [solutionFilePaths, setSolutionFilePaths] = useState<Set<string>>(new Set());
  const [consoleTab, setConsoleTab] = useState<"testcase" | "console" | "tests">("testcase");
  const [fullOutputOpen, setFullOutputOpen] = useState(false);
  const [expandedCases, setExpandedCases] = useState<Set<number>>(new Set());
  const [selectedCitationId, setSelectedCitationId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) return;
      try {
        const token = data.session.access_token;
        const [courseSummary, conceptDetail, map, masteryResponse] = await Promise.all([
          getCourse(courseId, token),
          getConceptDetail(courseId, slug, token),
          getCourseMap(courseId, token),
          getCourseMastery(courseId, token).catch(() => undefined)
        ]);
        if (cancelled) return;
        setCourse(courseSummary);
        setConcept(conceptDetail);
        setCourseMap(map);
        setMastery(masteryResponse);
        const starterFiles = conceptDetail.lesson?.starter_files ?? [];
        setFiles(starterFiles);
        setActiveFilePath(starterFiles[0]?.path);
        setTestResult(undefined);
        setScriptResult(undefined);
        setLabComplete(false);
        setScratchCode(defaultScratchScript(starterFiles));
        setInstructionsTab("lesson");
        setSolutionRevealed(false);
        setSolutionFilePaths(new Set());
        setConsoleTab("testcase");
        setAssessmentComplete(false);
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

  useEffect(() => {
    const cssWithHighlights = CSS as typeof CSS & { highlights?: { set: (name: string, highlight: unknown) => void; delete: (name: string) => void } };
    if (!cssWithHighlights.highlights) return;
    const style = document.createElement("style");
    style.textContent = "::highlight(canopy-selection) { background-color: rgba(25, 118, 210, 0.18); color: inherit; }";
    document.head.append(style);
    cssWithHighlights.highlights.delete("canopy-selection");
    if (!selectedRange) {
      return () => style.remove();
    }
    const HighlightConstructor = (window as typeof window & { Highlight?: new (range: Range) => unknown }).Highlight;
    if (!HighlightConstructor) return;
    cssWithHighlights.highlights.set("canopy-selection", new HighlightConstructor(selectedRange));
    return () => {
      cssWithHighlights.highlights?.delete("canopy-selection");
      style.remove();
    };
  }, [selectedRange]);

  useEffect(() => {
    function clearIfEmpty() {
      if (!window.getSelection()?.toString().trim()) setBubbleRect(undefined);
    }
    function dismissBubble() {
      setBubbleRect(undefined);
    }
    document.addEventListener("selectionchange", clearIfEmpty);
    window.addEventListener("scroll", dismissBubble, { capture: true });
    return () => {
      document.removeEventListener("selectionchange", clearIfEmpty);
      window.removeEventListener("scroll", dismissBubble, { capture: true });
    };
  }, []);

  function updateFile(path: string, content: string) {
    setFiles((current) => current.map((file) => file.path === path ? { ...file, content } : file));
  }

  function handleAskHelperForQuizItem(item: QuizItemPreview) {
    setSelectedText("");
    setSelectedRange(undefined);
    setSelectedParagraph(undefined);
    setBubbleRect(undefined);
    setFocusedQuizItem(item);
    setHelperOpen(true);
  }

  function captureSelection(event: React.MouseEvent<HTMLElement>) {
    const selection = window.getSelection();
    if (!selection?.rangeCount || !event.currentTarget.contains(selection.getRangeAt(0).commonAncestorContainer)) return;
    const text = selection.toString().trim();
    if (!text) return;
    setFocusedQuizItem(undefined);
    setSelectedRange(selection.getRangeAt(0).cloneRange());
    const nodeElement = selection.anchorNode instanceof Element ? selection.anchorNode : selection.anchorNode?.parentElement;
    const paragraph = nodeElement?.closest<HTMLElement>("[data-lesson-paragraph]");
    if (paragraph?.dataset.lessonParagraph && paragraph.dataset.lessonSource) {
      const range = selection.getRangeAt(0);
      const before = document.createRange();
      before.selectNodeContents(paragraph);
      before.setEnd(range.startContainer, range.startOffset);
      const occurrence = before.toString().split(text).length - 1;
      setSelectedParagraph({ id: paragraph.dataset.lessonParagraph, source: paragraph.dataset.lessonSource, occurrence });
    } else {
      setSelectedParagraph(undefined);
    }
    setSelectedText(text.slice(0, 6000));
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    setBubbleRect({
      top: Math.max(8, rect.top - 44),
      left: Math.min(Math.max(8, rect.left + rect.width / 2), window.innerWidth - 60),
    });
  }

  function handleCitationClick(citationId: string) {
    setSelectedCitationId(citationId);
  }

  function applyHelperRevision(replacement: string): boolean {
    if (!concept || !selectedText) return false;
    const target = selectedParagraph?.source ?? selectedText;
    const nextSummary = replaceVisiblePassage(concept.summary_markdown, target, replacement);
    const nextExplanation = concept.lesson ? replaceVisiblePassage(concept.lesson.explanation_markdown, target, replacement) : null;
    if (nextSummary === null && nextExplanation === null) {
      setErrorMessage("That passage no longer matches the lesson text. Select it again and ask the helper to revise it.");
      return false;
    }
    setConcept({
      ...concept,
      summary_markdown: nextSummary ?? concept.summary_markdown,
      lesson: concept.lesson ? { ...concept.lesson, explanation_markdown: nextExplanation ?? concept.lesson.explanation_markdown } : null,
    });
    setSelectedText(replacement);
    setSelectedParagraph((current) => current ? { ...current, source: replacement } : undefined);
    setLessonUpdateNotice(true);
    window.setTimeout(() => setLessonUpdateNotice(false), 3500);
    return true;
  }

  // Unlocking the solution adds it to the workspace as new, separately-named files rather
  // than overwriting whatever the learner had written -- their own files stay untouched,
  // and the solution files are fully editable/runnable tabs, not a read-only preview.
  function handleRevealSolution() {
    const solutionFiles = concept?.lesson?.solution_files ?? [];
    const additions = solutionFiles.map((file) => ({ path: solutionFilePath(file.path), content: file.content }));
    const additionPaths = new Set(additions.map((file) => file.path));
    setFiles((current) => [...current.filter((file) => !additionPaths.has(file.path)), ...additions]);
    setSolutionFilePaths(additionPaths);
    setActiveFilePath(additions[0]?.path);
    setTestResult(undefined);
    setScriptResult(undefined);
    setExpandedCases(new Set());
    setFullOutputOpen(false);
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
  // The scratch console imports the lab module Python-style ("from x import *") and the
  // sandbox only compiles the single scratch file for non-Python environments, so it
  // can't reach the lab's own functions there yet -- scoped to Python until that's solved.
  const scratchScriptSupported = !files[0] || monacoLanguageForPath(files[0].path) === "python";

  // The API rejects a run/submit unless the file set is *exactly* the lesson's starter
  // paths (HTTP 422 "Submit exactly the lesson starter files."). Revealing the solution
  // adds extra `_solution.py` tabs to `files` for viewing/editing, so submissions must be
  // filtered back down to just the starter paths -- the solution tabs never get graded.
  const starterFilePaths = new Set((concept?.lesson?.starter_files ?? []).map((file) => file.path));
  const submittableFiles = files.filter((file) => starterFilePaths.has(file.path));

  const conceptMastery: ConceptMastery | undefined = mastery?.concepts.find((entry) => entry.slug === slug);
  const masteryThreshold = mastery?.threshold ?? 0.95;

  async function refreshMastery() {
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) return;
      setMastery(await getCourseMastery(courseId, data.session.access_token));
    } catch {
      // Non-fatal: the meter just keeps its last value if a refresh fails.
    }
  }

  // courseMap is only fetched once on load, so its per-concept `completed` flags (the
  // checkmarks in the outline sidebar and course overview) would otherwise go stale for
  // the rest of the session the moment a lesson is finished. Refresh it alongside mastery
  // on every completion-relevant event so "done" shows up live, not just after a reload.
  async function refreshCourseMap() {
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) return;
      setCourseMap(await getCourseMap(courseId, data.session.access_token));
    } catch {
      // Non-fatal: the outline/module list just keeps its last known completion state.
    }
  }

  async function refreshProgress() {
    await Promise.all([refreshMastery(), refreshCourseMap()]);
  }

  // Run = visible checks only. Tight feedback loop, no mastery effect, no completion.
  async function handleRunTests() {
    setConsoleTab("tests");
    setRunning(true);
    setExpandedCases(new Set());
    setFullOutputOpen(false);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      setErrorMessage(undefined);
      setTestResult(await runLesson(courseId, slug, submittableFiles, data.session.access_token));
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Unable to run exercise tests.");
    } finally {
      setRunning(false);
    }
  }

  // Submit = full suite (visible + hidden). Records the applied-skill mastery observation
  // server-side, so we refresh the meter afterwards to show p(apply) move.
  async function handleSubmit() {
    setConsoleTab("tests");
    setSubmitting(true);
    setExpandedCases(new Set());
    setFullOutputOpen(false);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      setErrorMessage(undefined);
      const result = await submitLesson(courseId, slug, submittableFiles, data.session.access_token);
      setTestResult(result);
      if (result.passed) {
        setLabComplete(true);
        setCelebrateNonce((current) => current + 1);
      }
      await refreshProgress();
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Unable to submit your solution.");
    } finally {
      setSubmitting(false);
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
        await runLessonScript(courseId, slug, submittableFiles, { path: "scratch.py", content: scratchCode }, data.session.access_token)
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

  // Dev-only: answers this lesson's quizzes and submits its lab as an LLM standing in for
  // the learner, through the real grading/sandbox paths -- scoped to just this concept, so
  // it starts immediately instead of opening the course-wide auto-complete dialog.
  async function handleDemoFillLesson() {
    setDemoFilling(true);
    setErrorMessage(undefined);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const token = data.session.access_token;
      let job = await startDemoAutoComplete(
        courseId,
        { target: "mastered", correctRate: 1, conceptSlugs: [slug], includeQuizzes: true, includeLabs: true },
        token
      );
      while (job.state === "running") {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        job = await getDemoAutoCompleteStatus(courseId, job.job_id, token);
      }
      if (job.state === "failed") throw new Error(job.error ?? "Demo fill failed.");
      setReloadNonce((current) => current + 1);
      await refreshProgress();
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Unable to demo-fill this lesson.");
    } finally {
      setDemoFilling(false);
    }
  }

  // The undo for handleDemoFillLesson: wipes this concept's mastery/observations/
  // assignment state back to never-attempted.
  async function handleDemoClearLesson() {
    setDemoClearing(true);
    setErrorMessage(undefined);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      await clearDemoProgress(courseId, [slug], data.session.access_token);
      setReloadNonce((current) => current + 1);
      await refreshProgress();
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Unable to clear this lesson's demo progress.");
    } finally {
      setDemoClearing(false);
    }
  }

  if (state === "loading") {
    return (
      <PageShell maxWidth={{ xs: 1040, xl: helperOpen ? 1360 : 1040 }}>
        <CourseOutlineSidebar courseId={courseId} map={courseMap} activeSlug={slug} collapsed={outlineCollapsed} onToggle={() => setOutlineCollapsed((current) => !current)} />
        <LearningHelperSidebar courseId={courseId} slug={slug} selectedText={selectedText} selectedParagraph={selectedParagraph} focusedQuizItem={focusedQuizItem} workspaceFiles={submittableFiles} open={helperOpen} onToggle={() => setHelperOpen((current) => !current)} onClearSelection={() => { setSelectedText(""); setSelectedRange(undefined); setSelectedParagraph(undefined); setBubbleRect(undefined); setFocusedQuizItem(undefined); }} onApplyRevision={applyHelperRevision} />
        {bubbleRect ? <SelectionAskBubble rect={bubbleRect} onAsk={() => { setHelperOpen(true); setBubbleRect(undefined); }} /> : null}
        <Stack direction="row" sx={{ ml: { md: outlineCollapsed ? "56px" : "280px" }, mr: { xs: "56px", xl: helperOpen ? "360px" : "56px" }, alignItems: "center", gap: 1.5, color: "text.secondary" }}>
          <CircularProgress size={18} /> <Typography>Loading…</Typography>
        </Stack>
      </PageShell>
    );
  }
  if (state === "error") return <PageShell><CourseOutlineSidebar courseId={courseId} map={courseMap} activeSlug={slug} collapsed={outlineCollapsed} onToggle={() => setOutlineCollapsed((current) => !current)} /><LearningHelperSidebar courseId={courseId} slug={slug} selectedText={selectedText} selectedParagraph={selectedParagraph} focusedQuizItem={focusedQuizItem} workspaceFiles={submittableFiles} open={helperOpen} onToggle={() => setHelperOpen((current) => !current)} onClearSelection={() => { setSelectedText(""); setSelectedRange(undefined); setSelectedParagraph(undefined); setBubbleRect(undefined); setFocusedQuizItem(undefined); }} onApplyRevision={applyHelperRevision} />
        {bubbleRect ? <SelectionAskBubble rect={bubbleRect} onAsk={() => { setHelperOpen(true); setBubbleRect(undefined); }} /> : null}<Box sx={{ ml: { md: outlineCollapsed ? "56px" : "280px" }, mr: { xs: "56px", xl: helperOpen ? "360px" : "56px" } }}><Alert severity="error">{errorMessage ?? "We could not load this concept."}</Alert></Box></PageShell>;
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
    <Avatar
      variant="rounded"
      sx={{
        width: 32,
        height: 32,
        bgcolor: alpha(conceptKindColor(concept.kind), 0.15),
        color: conceptKindColor(concept.kind),
        "& .material-symbol": { fontSize: 17 },
      }}
    >
      <Icon name={conceptKindIcon(concept.kind)} />
    </Avatar>
  );

  const lessonSettingsMenu = (
    <SettingsMenu
      actions={[
        { label: regenerating ? "Regenerating…" : "Regenerate lesson", icon: "refresh", onClick: handleRegenerateLesson, disabled: regenerating },
        // The API 404s these outside local development regardless -- hidden here too so a
        // production build never even shows an action that can't work.
        ...(process.env.NODE_ENV === "development"
          ? [
              { label: demoFilling ? "Filling…" : "Demo: fill this lesson", icon: "smart_toy", onClick: () => void handleDemoFillLesson(), disabled: demoFilling || demoClearing },
              { label: demoClearing ? "Clearing…" : "Demo: clear this lesson", icon: "restart_alt", onClick: () => void handleDemoClearLesson(), disabled: demoFilling || demoClearing },
            ]
          : []),
      ]}
      label="Lesson settings"
    />
  );

  if (concept.kind !== "coding") {
    return (
      <PageShell maxWidth={{ xs: 1040, xl: helperOpen ? 1360 : 1040 }}>
        <LearningHelperSidebar courseId={courseId} slug={slug} selectedText={selectedText} selectedParagraph={selectedParagraph} focusedQuizItem={focusedQuizItem} workspaceFiles={submittableFiles} open={helperOpen} onToggle={() => setHelperOpen((current) => !current)} onClearSelection={() => { setSelectedText(""); setSelectedRange(undefined); setSelectedParagraph(undefined); setBubbleRect(undefined); setFocusedQuizItem(undefined); }} onApplyRevision={applyHelperRevision} />
        {bubbleRect ? <SelectionAskBubble rect={bubbleRect} onAsk={() => { setHelperOpen(true); setBubbleRect(undefined); }} /> : null}
        <CitationExcerptDialog courseId={courseId} citationId={selectedCitationId} onOpenChange={(open) => { if (!open) setSelectedCitationId(null); }} />
        <Box sx={{ ml: { md: outlineCollapsed ? "56px" : "280px" }, mr: { xs: "56px", xl: helperOpen ? "360px" : "56px" } }}>
        {breadcrumbs}
        <Box sx={{ display: "flex", gap: 3, alignItems: "flex-start" }}>
        <CourseOutlineSidebar courseId={courseId} map={courseMap} activeSlug={slug} collapsed={outlineCollapsed} onToggle={() => setOutlineCollapsed((current) => !current)} />
        <Box sx={{ flex: 1, minWidth: 0 }}>
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
          <PrerequisiteReview courseId={courseId} slug={slug} />
          <Box onMouseUp={captureSelection}><MarkdownText citations={concept.citations} paragraphGroup="summary" onCitationClick={handleCitationClick}>{concept.summary_markdown}</MarkdownText></Box>
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
              <Box onMouseUp={captureSelection}><LessonBody
                courseId={courseId}
                slug={slug}
                markdown={concept.lesson.explanation_markdown}
                citations={concept.citations}
                examples={concept.lesson.worked_examples ?? []}
                quizItems={concept.lesson.quiz_items ?? []}
                quizMaxAttempts={concept.lesson.quiz_max_attempts}
                onQuizAnswered={refreshProgress}
                paragraphGroup="lesson"
                onCitationClick={handleCitationClick}
                onAskHelperForQuiz={handleAskHelperForQuizItem}
              /></Box>
              <QuizSection
                courseId={courseId}
                slug={slug}
                items={(concept.lesson.quiz_items ?? []).filter(
                  (_, index) => !markerReferencedQuizIndexes(concept.lesson?.explanation_markdown ?? "").has(index)
                )}
                maxAttempts={concept.lesson.quiz_max_attempts}
                title={concept.kind === "assessment" ? "Topic assessment" : undefined}
                onComplete={concept.kind === "assessment" ? () => setAssessmentComplete(true) : undefined}
                onAnswered={refreshProgress}
                onAskHelper={handleAskHelperForQuizItem}
              />
              {conceptMastery ? <MasteryCard concept={conceptMastery} threshold={masteryThreshold} /> : null}
              {assessmentComplete ? <LessonComplete courseId={courseId} map={courseMap} slug={slug} title="Assessment" /> : null}
            </Stack>
          ) : null}
          <LessonNavigation courseId={courseId} map={courseMap} activeSlug={slug} />
        </Stack>
        </Box>
        </Box>
        </Box>
      </PageShell>
    );
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <CourseOutlineSidebar courseId={courseId} map={courseMap} activeSlug={slug} collapsed={outlineCollapsed} onToggle={() => setOutlineCollapsed((current) => !current)} />
      <LearningHelperSidebar courseId={courseId} slug={slug} selectedText={selectedText} selectedParagraph={selectedParagraph} focusedQuizItem={focusedQuizItem} workspaceFiles={submittableFiles} open={helperOpen} onToggle={() => setHelperOpen((current) => !current)} onClearSelection={() => { setSelectedText(""); setSelectedRange(undefined); setSelectedParagraph(undefined); setBubbleRect(undefined); setFocusedQuizItem(undefined); }} onApplyRevision={applyHelperRevision} />
        {bubbleRect ? <SelectionAskBubble rect={bubbleRect} onAsk={() => { setHelperOpen(true); setBubbleRect(undefined); }} /> : null}
      <CitationExcerptDialog courseId={courseId} citationId={selectedCitationId} onOpenChange={(open) => { if (!open) setSelectedCitationId(null); }} />
      <Dialog open={solutionConfirmOpen} onClose={() => setSolutionConfirmOpen(false)}>
        <DialogTitle>Unlock the reference solution?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Seeing the reference solution before you&apos;ve solved it yourself will spoil the exercise. It&apos;s added as new file(s)
            in your workspace, alongside your own -- your existing work is untouched, and you can run or submit the solution files too.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button variant="text" onClick={() => setSolutionConfirmOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleRevealSolution}>Unlock solution</Button>
        </DialogActions>
      </Dialog>

      {errorMessage ? <Alert severity="error" sx={{ mx: 3, mt: 1.5 }}>{errorMessage}</Alert> : null}

      {concept.lesson && concept.lesson.status === "built" ? (
        <Box sx={{ flex: 1, minHeight: 0, display: "flex", pl: { md: outlineCollapsed ? "56px" : "280px" }, pr: { xs: "56px", xl: helperOpen ? "360px" : "56px" } }}>
          <Box sx={{ flex: codeCollapsed ? 1 : "0 1 420px", minWidth: 280, overflowY: "auto", p: "24px 24px 48px", borderRight: 1, borderColor: "divider", display: "grid", gap: 3, alignContent: "start" }}>
            <Stack direction="row" sx={{ alignItems: "flex-start", justifyContent: "space-between", gap: 1 }}>
              <Stack sx={{ minWidth: 0, gap: 0.25 }}>
                <Typography variant="overline" color="text.secondary">{conceptKindLabel(concept.kind)}</Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }} noWrap>{concept.title}</Typography>
              </Stack>
              {lessonSettingsMenu}
            </Stack>
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
                <PrerequisiteReview courseId={courseId} slug={slug} />
                <Box onMouseUp={captureSelection}><MarkdownText citations={concept.citations} paragraphGroup="summary" onCitationClick={handleCitationClick}>{concept.summary_markdown}</MarkdownText></Box>

                {concept.lesson.explanation_markdown ? (
                  <Stack sx={{ gap: 1.5 }} onMouseUp={captureSelection}>
                    <Divider textAlign="left"><Typography variant="overline" color="text.secondary">Lesson</Typography></Divider>
                    <LessonBody
                      courseId={courseId}
                      slug={slug}
                      markdown={concept.lesson.explanation_markdown}
                      citations={concept.citations}
                      examples={concept.lesson.worked_examples ?? []}
                      quizItems={concept.lesson.quiz_items ?? []}
                      quizMaxAttempts={concept.lesson.quiz_max_attempts}
                      paragraphGroup="lesson"
                      onCitationClick={handleCitationClick}
                      onAskHelperForQuiz={handleAskHelperForQuizItem}
                    />
                  </Stack>
                ) : (
                  <WorkedExamples examples={concept.lesson.worked_examples} citations={concept.citations} onCitationClick={handleCitationClick} />
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
                  onAnswered={refreshProgress}
                  onAskHelper={handleAskHelperForQuizItem}
                />
                {conceptMastery ? <MasteryCard concept={conceptMastery} threshold={masteryThreshold} /> : null}
                {labComplete ? <LessonComplete courseId={courseId} map={courseMap} slug={slug} title="Lab" /> : null}
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
                  The reference solution was added as new file(s) in the editor on the right -- your own files are untouched.
                </Alert>
                <List disablePadding sx={{ display: "grid", gap: 1 }}>
                  {concept.lesson.solution_files.map((file) => {
                    const path = solutionFilePath(file.path);
                    return (
                      <ListItemButton
                        key={path}
                        selected={activeFilePath === path}
                        onClick={() => setActiveFilePath(path)}
                        sx={{ border: 1, borderColor: "divider", borderRadius: 1.5 }}
                      >
                        <ListItemIcon sx={{ minWidth: 36, color: "success.main" }}><Icon name="auto_awesome" /></ListItemIcon>
                        <ListItemText primary={path} slotProps={{ primary: { sx: { fontFamily: monoFont, fontSize: "0.85rem" } } }} />
                      </ListItemButton>
                    );
                  })}
                </List>
              </Stack>
            )}
          </Box>

          <ThemeProvider theme={labTheme}>
            <Box
              sx={{
                flex: codeCollapsed ? "0 0 0px" : 1,
                minWidth: codeCollapsed ? 0 : 360,
                display: codeCollapsed ? "none" : "flex",
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
                  {files.map((file) => {
                    const isSolutionFile = solutionFilePaths.has(file.path);
                    return (
                      <Tab
                        key={file.path}
                        value={file.path}
                        label={
                          <Stack direction="row" sx={{ alignItems: "center", gap: 0.75 }}>
                            <Icon name={isSolutionFile ? "auto_awesome" : "code"} /> {file.path}
                          </Stack>
                        }
                        sx={{
                          minHeight: 38,
                          textTransform: "none",
                          fontFamily: monoFont,
                          fontSize: "0.78rem",
                          color: isSolutionFile ? "success.main" : undefined
                        }}
                      />
                    );
                  })}
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
                  <Button size="small" variant="outlined" color="success" startIcon={<Icon name="play_arrow" />} onClick={handleRunTests} loading={running} sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700 }}>
                    Run
                  </Button>
                  <Button size="small" variant="contained" color="success" startIcon={<Icon name="task_alt" />} onClick={handleSubmit} loading={submitting} sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700 }}>
                    Submit
                  </Button>
                  <IconButton size="small" onClick={() => setCodeCollapsed(true)} aria-label="Collapse code">
                    <Icon name="chevron_right" />
                  </IconButton>
                </Stack>
              </Stack>
              {activeFileIsReadOnly ? (
                <Typography variant="body2" color="text.secondary" sx={{ px: 2, pt: 1 }}>
                  This is one of the checks your solution is graded against (read-only, but always included when you Submit).
                </Typography>
              ) : activeFile && solutionFilePaths.has(activeFile.path) ? (
                <Typography variant="body2" color="text.secondary" sx={{ px: 2, pt: 1 }}>
                  This is the reference solution, editable for experimentation -- Run and Submit always test your own files, not this one.
                </Typography>
              ) : null}
              <Box sx={{ flex: 1, minHeight: 0 }}>
                {activeFile ? (
                  <MonacoEditor
                    height="100%"
                    language={monacoLanguageForPath(activeFile.path)}
                    theme="vs-dark"
                    path={activeFile.path}
                    value={activeFile.content}
                    onChange={(content) => { if (!activeFileIsReadOnly) updateFile(activeFile.path, content ?? ""); }}
                    options={{ ...editorOptionsBase, automaticLayout: true, readOnly: activeFileIsReadOnly }}
                  />
                ) : null}
              </Box>

              <Box sx={{ position: "relative", flexShrink: 0, height: 260, display: "flex", flexDirection: "column", borderTop: 1, borderColor: "divider", bgcolor: "background.paper" }}>
                {celebrateNonce > 0 && labComplete && consoleTab === "tests" ? <ConfettiBurst key={celebrateNonce} /> : null}
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
                        {testResult ? <TabDot ok={testResult.passed} /> : null}
                      </Stack>
                    }
                    sx={{ minHeight: 34, textTransform: "none" }}
                  />
                </Tabs>
                <Box sx={{ flex: 1, minHeight: 0, overflowY: "auto", bgcolor: "background.default", p: "12px 14px", display: "grid", gap: 1.25, alignContent: "start" }}>
                  {consoleTab === "testcase" && !scratchScriptSupported ? (
                    <Alert severity="info">Scratch scripts are only available for Python labs right now -- use Run/Submit below to test your code.</Alert>
                  ) : consoleTab === "testcase" ? (
                    <>
                      <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                        <Typography variant="body2" color="text.secondary">
                          Scratch script: call your code with any input and hit Run script to see what it prints. Never affects grading or mastery.
                        </Typography>
                        <Button size="small" variant="outlined" color="success" startIcon={<Icon name="play_arrow" />} onClick={handleRunScript} loading={runningScript} sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700, flexShrink: 0 }}>
                          Run script
                        </Button>
                      </Stack>
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
                  ) : testResult ? (
                    <>
                      <Typography variant="body2" color="text.secondary">
                        Run checks the visible tests only. Submit swaps in the full suite (hidden checks included) and updates your Apply mastery.
                      </Typography>
                      {testResult.prerequisite_recommendation ? (
                        <PrerequisiteNudge courseId={courseId} recommendation={testResult.prerequisite_recommendation} />
                      ) : null}
                      {(() => {
                        const cases = parsePytestCases(testResult.output);
                        return cases.length > 0 ? (
                          <Stack component="ul" sx={{ listStyle: "none", m: 0, p: 0, gap: "2px" }}>
                            {cases.map((testCase, index) => {
                              const caseExpanded = expandedCases.has(index);
                              return (
                                <Box component="li" key={index}>
                                  <Stack
                                    direction="row"
                                    onClick={testCase.output ? () => {
                                      setExpandedCases((current) => {
                                        const next = new Set(current);
                                        if (next.has(index)) next.delete(index); else next.add(index);
                                        return next;
                                      });
                                    } : undefined}
                                    sx={{
                                      alignItems: "center", gap: 1, px: 1, py: 0.75, borderRadius: 1, fontSize: "0.85rem",
                                      cursor: testCase.output ? "pointer" : "default",
                                      color: testCase.status === "passed" ? "success.light" : testCase.status === "skipped" ? "text.secondary" : "error.light"
                                    }}
                                  >
                                    <Icon name={testCase.status === "passed" ? "check_circle" : testCase.status === "skipped" ? "remove_circle" : "cancel"} />
                                    <Typography variant="body2" sx={{ color: "inherit", flex: 1 }}>{testCase.name}</Typography>
                                    {testCase.output ? <Icon name={caseExpanded ? "expand_less" : "expand_more"} /> : null}
                                  </Stack>
                                  {testCase.output ? (
                                    <Collapse in={caseExpanded}>
                                      <Box
                                        component="pre"
                                        sx={{
                                          m: "0 0 4px", p: 1.5, borderRadius: 1, overflowX: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word",
                                          fontSize: "0.78rem", bgcolor: "#131313", color: "#ddd", borderLeft: 3, borderColor: "error.main"
                                        }}
                                      >
                                        {testCase.output}
                                      </Box>
                                    </Collapse>
                                  ) : null}
                                </Box>
                              );
                            })}
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
                          {fullOutputOpen ? "Hide full raw output" : "Full raw output"}
                        </Button>
                        <Collapse in={fullOutputOpen}>
                          <Box
                            component="pre"
                            sx={{
                              mt: 1, mb: 0, p: 1.75, borderRadius: 1, overflowX: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word",
                              fontSize: "0.82rem", bgcolor: "#131313", color: "#ddd",
                              borderLeft: 3, borderColor: testResult.passed ? "success.main" : "error.main"
                            }}
                          >
                            {testResult.output}
                          </Box>
                        </Collapse>
                      </Box>
                    </>
                  ) : (
                    <Typography variant="body2" color="text.secondary">Hit Run or Submit above to see check results here.</Typography>
                  )}
                </Box>
              </Box>
            </Box>
            {codeCollapsed ? (
              <Stack sx={{ width: 56, flexShrink: 0, alignItems: "center", pt: 1.5, bgcolor: "background.paper", borderLeft: 1, borderColor: "divider" }}>
                <IconButton size="small" onClick={() => setCodeCollapsed(false)} aria-label="Expand code">
                  <Icon name="chevron_left" />
                </IconButton>
              </Stack>
            ) : null}
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
