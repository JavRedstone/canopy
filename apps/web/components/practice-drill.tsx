"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Paper from "@mui/material/Paper";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Alert from "@mui/material/Alert";
import Chip from "@mui/material/Chip";
import Collapse from "@mui/material/Collapse";
import LinearProgress from "@mui/material/LinearProgress";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import { alpha } from "@mui/material/styles";
import {
  PracticeGradeResponse,
  PracticeQuestion,
  PracticeSessionOptions,
  QuizAnswerRequest,
  answerPracticeQuestion,
  getPracticeSession,
  topUpPracticePool
} from "@/lib/api";
import { CanopyLoader } from "@/components/canopy-loader";
import { Icon } from "@/components/icon";
import { MarkdownText } from "@/components/markdown-text";
import { QuizOptionList } from "@/components/quiz";
import { createClient } from "@/lib/supabase/client";

type Order = NonNullable<PracticeSessionOptions["order"]>;
type Filter = NonNullable<PracticeSessionOptions["filter"]>;

interface SessionConfig {
  length: number;
  order: Order;
  filter: Filter;
}

const SESSION_LENGTHS = [5, 10, 20] as const;
// "Endless" is not a special server mode -- it just keeps asking for another batch when the
// current one runs out, so the engine's non-repeat rotation still applies across batches.
const ENDLESS = 0;
const BATCH_SIZE = 10;

// What you get without touching anything: a short shuffled set of questions you haven't seen.
const DEFAULT_CONFIG: SessionConfig = { length: 10, order: "shuffle", filter: "unseen" };

const ORDER_LABELS: Record<Order, string> = {
  shuffle: "Shuffle",
  weakest: "Weakest first",
  course: "Course order"
};

// Terse on purpose: the toggle labels the choice, and describeSession() below spells out
// what it means, so these don't have to wrap onto two lines to explain themselves.
const FILTER_LABELS: Record<Filter, string> = {
  unseen: "New",
  all: "All",
  missed: "Missed"
};

const ORDER_PHRASES: Record<Order, string> = {
  shuffle: "in random order",
  weakest: "weakest concepts first",
  course: "in course order"
};

const FILTER_PHRASES: Record<Filter, string> = {
  unseen: "you haven't seen yet",
  all: "from the whole pool",
  missed: "you've missed before"
};

/** Turns the three toggles into one plain sentence, so the configured session is legible
 *  without mentally combining "10" + "Shuffle" + "New questions". */
function describeSession(config: SessionConfig): string {
  const length = config.length === ENDLESS ? "Endless practice" : `${config.length} questions`;
  return `${length} ${FILTER_PHRASES[config.filter]}, ${ORDER_PHRASES[config.order]}.`;
}

function OptionGroup<T extends string | number>({
  label,
  icon,
  value,
  options,
  onChange
}: {
  label: string;
  icon: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <Box sx={{ display: "grid", gap: 0.75, alignContent: "start", minWidth: 0 }}>
      <Stack direction="row" sx={{ alignItems: "center", gap: 0.5, color: "text.secondary", "& .material-symbol": { fontSize: 16 } }}>
        <Icon name={icon} />
        <Typography variant="overline">{label}</Typography>
      </Stack>
      <ToggleButtonGroup
        size="small"
        exclusive
        fullWidth
        value={value}
        onChange={(_event, next) => { if (next !== null) onChange(next as T); }}
        sx={{
          "& .MuiToggleButton-root": {
            py: 0.65,
            px: 1,
            textTransform: "none",
            fontSize: "0.78rem",
            lineHeight: 1.2,
            borderColor: "divider",
            // MUI's default selected state is a barely-darker grey; at this size the active
            // choice has to be unmistakable at a glance.
            "&.Mui-selected": {
              bgcolor: "primary.main",
              color: "primary.contrastText",
              fontWeight: 600,
              "&:hover": { bgcolor: "primary.main" }
            }
          }
        }}
      >
        {options.map((option) => (
          <ToggleButton key={String(option.value)} value={option.value}>{option.label}</ToggleButton>
        ))}
      </ToggleButtonGroup>
    </Box>
  );
}

function answerFor(question: PracticeQuestion, selected: number[], text: string): QuizAnswerRequest | null {
  if (question.kind === "mcq") return selected.length === 1 ? { selected_option_index: selected[0] } : null;
  if (question.kind === "multi_select") return selected.length > 0 ? { selected_option_indices: selected } : null;
  return text.trim() ? { answer_text: text } : null;
}

async function accessToken(): Promise<string> {
  const { data } = await createClient().auth.getSession();
  if (!data.session) throw new Error("Your session has expired. Please sign in again.");
  return data.session.access_token;
}

/**
 * One drill question. Much simpler than the graded `QuizQuestion`: practice has no attempt
 * cap, withholds nothing, and never records a miss against mastery, so the whole
 * retry/withhold/attempts-remaining state machine that question carries has no meaning here.
 * Answer, see everything, move on.
 */
function PracticeQuestionCard({
  courseId,
  question,
  showConcept,
  onAnswered
}: {
  courseId: string;
  question: PracticeQuestion;
  showConcept: boolean;
  onAnswered: (grade: PracticeGradeResponse) => void;
}) {
  const [selected, setSelected] = useState<number[]>([]);
  const [text, setText] = useState("");
  const [grade, setGrade] = useState<PracticeGradeResponse>();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>();

  const answered = grade !== undefined;
  const answer = answerFor(question, selected, text);
  const isChoice = question.kind === "mcq" || question.kind === "multi_select";

  function toggleOption(optionIndex: number) {
    if (answered) return;
    if (question.kind === "mcq") {
      setSelected([optionIndex]);
    } else {
      setSelected((current) =>
        current.includes(optionIndex) ? current.filter((entry) => entry !== optionIndex) : [...current, optionIndex].sort((a, b) => a - b)
      );
    }
  }

  async function handleSubmit() {
    if (!answer || answered) return;
    setSubmitting(true);
    setError(undefined);
    try {
      const result = await answerPracticeQuestion(courseId, question.id, answer, await accessToken());
      setGrade(result);
      onAnswered(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to check your answer.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Paper variant="outlined" sx={{ p: 2, display: "grid", gap: 1.5, bgcolor: (theme) => alpha(theme.palette.info.main, 0.03) }}>
      <Stack direction="row" sx={{ gap: 1, alignItems: "baseline", flexWrap: "wrap" }}>
        <Box sx={{ flex: 1, minWidth: 240 }}><MarkdownText>{question.prompt_markdown}</MarkdownText></Box>
        {showConcept ? <Chip size="small" variant="outlined" label={question.concept_title} /> : null}
      </Stack>

      {isChoice ? (
        <QuizOptionList
          kind={question.kind}
          options={question.options}
          selected={selected}
          disabled={answered}
          optionGrades={grade?.options}
          revealAll
          onToggle={toggleOption}
        />
      ) : question.kind === "fill" ? (
        <TextField
          size="small"
          placeholder="Your answer"
          value={text}
          disabled={answered}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") void handleSubmit(); }}
        />
      ) : (
        <TextField
          multiline
          rows={4}
          placeholder="Write a short answer in your own words…"
          value={text}
          disabled={answered}
          onChange={(event) => setText(event.target.value)}
        />
      )}

      {error ? <Alert severity="error">{error}</Alert> : null}

      {!answered ? (
        <Box>
          <Button variant="outlined" onClick={handleSubmit} disabled={!answer || submitting}>
            {submitting ? "Checking…" : "Check answer"}
          </Button>
        </Box>
      ) : (
        <AnimatePresence>
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
            <Alert severity={grade.correct ? "success" : "info"} sx={{ display: "grid", gap: 1 }}>
              <Typography sx={{ fontWeight: 700 }}>{grade.correct ? "Correct" : "Not this time"}</Typography>
              {grade.feedback_markdown ? <MarkdownText>{grade.feedback_markdown}</MarkdownText> : null}
              {!grade.correct && grade.correct_answers.length > 0 ? (
                <Typography variant="body2">
                  Accepted answer{grade.correct_answers.length > 1 ? "s" : ""}: {grade.correct_answers.join(", ")}
                </Typography>
              ) : null}
              {grade.explanation_markdown ? <MarkdownText>{grade.explanation_markdown}</MarkdownText> : null}
              {!grade.correct ? (
                <Typography variant="caption" color="text.secondary">
                  Practice is low-stakes, so a miss here never counts against your mastery. You&apos;ll see this one again.
                </Typography>
              ) : null}
            </Alert>
          </motion.div>
        </AnimatePresence>
      )}
    </Paper>
  );
}

/**
 * The drill surface, used from two places over the same machinery: pinned to a single
 * concept on the concept page, or course-wide on the course page.
 *
 * It opens directly on a question rather than a setup screen. Practice is meant to be the
 * low-friction thing you do without deciding anything, so the defaults load immediately and
 * the session options sit behind a toggle for the minority of sessions that want them.
 * Changing one restarts the batch in place, since a half-answered set chosen under different
 * options is not a set anyone asked for.
 */
export function PracticeDrill({
  courseId,
  conceptSlug,
  onMasteryChange
}: {
  courseId: string;
  // Set on the concept page: pins the session to one concept.
  conceptSlug?: string;
  onMasteryChange?: () => void;
}) {
  const [config, setConfig] = useState<SessionConfig>(DEFAULT_CONFIG);
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [questions, setQuestions] = useState<PracticeQuestion[]>([]);
  const [position, setPosition] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [scopeEmpty, setScopeEmpty] = useState(false);
  const [lowConcepts, setLowConcepts] = useState<string[]>([]);
  const [toppingUp, setToppingUp] = useState(false);
  const [toppedUp, setToppedUp] = useState(false);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);

  const loadBatch = useCallback(
    async (session: SessionConfig, append: boolean) => {
      setLoading(true);
      setError(undefined);
      try {
        const result = await getPracticeSession(
          courseId,
          {
            scope: conceptSlug ? "concepts" : "done",
            ids: conceptSlug ? [conceptSlug] : undefined,
            // Endless pulls a batch at a time and asks again when it runs dry.
            count: session.length === ENDLESS ? BATCH_SIZE : session.length,
            order: session.order,
            filter: session.filter
          },
          await accessToken()
        );
        setScopeEmpty(result.scope_empty);
        setLowConcepts(result.concepts_low_on_questions);
        setQuestions((current) => (append ? [...current, ...result.questions] : result.questions));
        return result.questions.length;
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Unable to load practice questions.");
        return 0;
      } finally {
        setLoading(false);
      }
    },
    [courseId, conceptSlug]
  );

  const startSession = useCallback(
    async (session: SessionConfig) => {
      setPosition(0);
      setAnsweredCount(0);
      setCorrectCount(0);
      setToppedUp(false);
      await loadBatch(session, false);
    },
    [loadBatch]
  );

  const startedRef = useRef<string>(undefined);
  useEffect(() => {
    // Load the first batch on mount so the panel opens on a question, not a setup screen.
    // Guarded by identity rather than left to fire on every option change -- those reload
    // explicitly through changeConfig, and re-firing here would double-fetch each toggle.
    const identity = `${courseId}:${conceptSlug ?? ""}`;
    if (startedRef.current === identity) return;
    startedRef.current = identity;
    void startSession(DEFAULT_CONFIG);
  }, [courseId, conceptSlug, startSession]);

  function changeConfig(patch: Partial<SessionConfig>) {
    const next = { ...config, ...patch };
    setConfig(next);
    void startSession(next);
  }

  function handleAnswered(grade: PracticeGradeResponse) {
    setAnsweredCount((current) => current + 1);
    if (grade.correct) {
      setCorrectCount((current) => current + 1);
      // Only a correct answer can move the estimate, so only refresh the meter then.
      if (grade.p_understand !== null && grade.p_understand !== undefined) onMasteryChange?.();
    }
  }

  async function handleNext() {
    const nextPosition = position + 1;
    if (nextPosition >= questions.length && config.length === ENDLESS) {
      const added = await loadBatch(config, true);
      if (added === 0) {
        setPosition(nextPosition);
        return;
      }
    }
    setPosition(nextPosition);
  }

  async function handleTopUp() {
    setToppingUp(true);
    setError(undefined);
    try {
      await topUpPracticePool(courseId, conceptSlug ? [conceptSlug] : lowConcepts, await accessToken());
      setToppedUp(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to request more questions.");
    } finally {
      setToppingUp(false);
    }
  }

  const current = questions[position];
  const finished = !loading && !current;
  const progress = questions.length > 0 ? Math.min((position / questions.length) * 100, 100) : 0;

  return (
    <Stack sx={{ gap: 1.5 }}>
      <Stack direction="row" sx={{ gap: 1, alignItems: "center", flexWrap: "wrap" }}>
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
          {answeredCount > 0 ? `${correctCount} of ${answeredCount} correct` : "Low-stakes drilling. A miss never counts against you"}
        </Typography>
        <Button
          size="small"
          variant="text"
          startIcon={<Icon name="tune" />}
          onClick={() => setOptionsOpen((open) => !open)}
        >
          Options
        </Button>
      </Stack>

      <Collapse in={optionsOpen} unmountOnExit>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: (theme) => alpha(theme.palette.primary.main, 0.015) }}>
          {/* Uneven columns: Order carries the longest labels, Questions the shortest. */}
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1.1fr 1.3fr 1fr" }, gap: { xs: 2, sm: 2.5 } }}>
            <OptionGroup
              label="Length"
              icon="tag"
              value={config.length}
              options={[...SESSION_LENGTHS.map((option) => ({ value: option, label: String(option) })), { value: ENDLESS, label: "Endless" }]}
              onChange={(length) => changeConfig({ length })}
            />
            <OptionGroup
              label="Order"
              icon="shuffle"
              value={config.order}
              options={(Object.keys(ORDER_LABELS) as Order[]).map((option) => ({ value: option, label: ORDER_LABELS[option] }))}
              onChange={(order) => changeConfig({ order })}
            />
            <OptionGroup
              label="Questions"
              icon="filter_alt"
              value={config.filter}
              options={(Object.keys(FILTER_LABELS) as Filter[]).map((option) => ({ value: option, label: FILTER_LABELS[option] }))}
              onChange={(filter) => changeConfig({ filter })}
            />
          </Box>

          {/* Three separate toggles don't add up to an obvious result, so say the outcome plainly. */}
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2, pt: 1.5, borderTop: 1, borderColor: "divider" }}>
            {describeSession(config)}
          </Typography>
        </Paper>
      </Collapse>

      {/* Only once there is progress to show. At 0% this rendered as a bare grey track that
          read as a stray divider between the options panel and the question card. */}
      {config.length !== ENDLESS && progress > 0 ? (
        <LinearProgress
          variant="determinate"
          value={progress}
          sx={{ height: 6, borderRadius: 999, bgcolor: "action.hover", "& .MuiLinearProgress-bar": { borderRadius: 999 } }}
        />
      ) : null}

      {error ? <Alert severity="error">{error}</Alert> : null}
      {loading && !current ? <CanopyLoader label="Loading questions…" size={44} py={4} /> : null}

      {current ? (
        <>
          <PracticeQuestionCard
            key={current.id}
            courseId={courseId}
            question={current}
            showConcept={!conceptSlug}
            onAnswered={handleAnswered}
          />
          <Box>
            <Button variant="outlined" onClick={handleNext} disabled={loading}>Next question</Button>
          </Box>
        </>
      ) : null}

      {finished ? (
        <Paper variant="outlined" sx={{ p: 2, display: "grid", gap: 1.5 }}>
          {scopeEmpty ? (
            <>
              <Typography sx={{ fontWeight: 700 }}>Nothing to practise yet</Typography>
              <Typography variant="body2" color="text.secondary">
                Practice draws on lessons you&apos;ve already started. Work through a lesson first and its questions will show up here.
              </Typography>
            </>
          ) : questions.length === 0 && config.filter === "unseen" ? (
            <>
              <Typography sx={{ fontWeight: 700 }}>You&apos;ve seen every question here</Typography>
              <Typography variant="body2" color="text.secondary">
                {toppedUp
                  ? "More questions are being written now. Check back in a moment."
                  : "Ask for a fresh batch, or switch “Questions” to Everything to drill the ones you've already answered."}
              </Typography>
              {!toppedUp ? (
                <Box>
                  <Button variant="contained" onClick={handleTopUp} disabled={toppingUp}>
                    {toppingUp ? "Requesting…" : "Write me more questions"}
                  </Button>
                </Box>
              ) : null}
            </>
          ) : questions.length === 0 ? (
            <>
              <Typography sx={{ fontWeight: 700 }}>No questions match</Typography>
              <Typography variant="body2" color="text.secondary">
                {config.filter === "missed" ? "You haven't missed anything here yet." : "There are no questions in this scope yet."}
              </Typography>
            </>
          ) : (
            <>
              <Typography sx={{ fontWeight: 700 }}>Session complete</Typography>
              <Typography variant="body2" color="text.secondary">{correctCount} of {answeredCount} correct.</Typography>
            </>
          )}
          <Box>
            <Button variant="outlined" onClick={() => void startSession(config)} disabled={loading}>
              {questions.length === 0 ? "Try again" : "New set"}
            </Button>
          </Box>
        </Paper>
      ) : null}
    </Stack>
  );
}
