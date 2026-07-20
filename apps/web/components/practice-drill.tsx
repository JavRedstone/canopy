"use client";

import { useCallback, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Paper from "@mui/material/Paper";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Alert from "@mui/material/Alert";
import Chip from "@mui/material/Chip";
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
import { Icon } from "@/components/icon";
import { MarkdownText } from "@/components/markdown-text";
import { QuizOptionList } from "@/components/quiz";
import { createClient } from "@/lib/supabase/client";

const SESSION_LENGTHS = [5, 10, 20] as const;
// "Endless" is not a special server mode -- it just keeps asking for another batch when the
// current one runs out, so the engine's non-repeat rotation still applies across batches.
const ENDLESS = 0;

type Order = NonNullable<PracticeSessionOptions["order"]>;
type Filter = NonNullable<PracticeSessionOptions["filter"]>;

const ORDER_LABELS: Record<Order, string> = {
  shuffle: "Shuffle",
  weakest: "Weakest first",
  course: "Course order"
};

const FILTER_LABELS: Record<Filter, string> = {
  unseen: "New questions",
  all: "Everything",
  missed: "Ones I missed"
};

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
                  Practice is low-stakes — a miss here never counts against your mastery. You&apos;ll see this one again.
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
 * concept on the concept page, or course-wide with a scope picker on the course page.
 */
export function PracticeDrill({
  courseId,
  conceptSlug,
  onMasteryChange
}: {
  courseId: string;
  // Set on the concept page: pins the session to one concept and hides the scope picker.
  conceptSlug?: string;
  onMasteryChange?: () => void;
}) {
  const [length, setLength] = useState<number>(10);
  const [order, setOrder] = useState<Order>("shuffle");
  const [filter, setFilter] = useState<Filter>("unseen");
  const [questions, setQuestions] = useState<PracticeQuestion[]>([]);
  const [position, setPosition] = useState(0);
  const [started, setStarted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [scopeEmpty, setScopeEmpty] = useState(false);
  const [lowConcepts, setLowConcepts] = useState<string[]>([]);
  const [toppingUp, setToppingUp] = useState(false);
  const [toppedUp, setToppedUp] = useState(false);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);

  const loadBatch = useCallback(
    async (append: boolean) => {
      setLoading(true);
      setError(undefined);
      try {
        const session = await getPracticeSession(
          courseId,
          {
            scope: conceptSlug ? "concepts" : "done",
            ids: conceptSlug ? [conceptSlug] : undefined,
            // Endless pulls a full batch at a time and asks again when it runs dry.
            count: length === ENDLESS ? 10 : length,
            order,
            filter
          },
          await accessToken()
        );
        setScopeEmpty(session.scope_empty);
        setLowConcepts(session.concepts_low_on_questions);
        setQuestions((current) => (append ? [...current, ...session.questions] : session.questions));
        if (!append) setPosition(0);
        return session.questions.length;
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Unable to load practice questions.");
        return 0;
      } finally {
        setLoading(false);
      }
    },
    [courseId, conceptSlug, length, order, filter]
  );

  async function handleStart() {
    setStarted(true);
    setAnsweredCount(0);
    setCorrectCount(0);
    setToppedUp(false);
    await loadBatch(false);
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
    if (nextPosition < questions.length) {
      setPosition(nextPosition);
      return;
    }
    if (length === ENDLESS) {
      const added = await loadBatch(true);
      if (added > 0) setPosition(nextPosition);
      return;
    }
    setPosition(nextPosition);
  }

  async function handleTopUp() {
    setToppingUp(true);
    setError(undefined);
    try {
      const slugs = conceptSlug ? [conceptSlug] : lowConcepts;
      await topUpPracticePool(courseId, slugs, await accessToken());
      setToppedUp(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to request more questions.");
    } finally {
      setToppingUp(false);
    }
  }

  function reconfigure(apply: () => void) {
    // Changing an option invalidates the batch on screen, so drop back to the setup card
    // rather than mixing questions chosen under two different configurations.
    apply();
    setStarted(false);
    setQuestions([]);
  }

  const current = questions[position];
  const finished = started && !loading && !current;

  if (!started) {
    return (
      <Paper variant="outlined" sx={{ p: 2, display: "grid", gap: 2 }}>
        <Box sx={{ display: "grid", gap: 0.5 }}>
          <Typography sx={{ fontWeight: 700 }}>Practice</Typography>
          <Typography variant="body2" color="text.secondary">
            Low-stakes drilling{conceptSlug ? " on this concept" : " across what you've worked through"}. Getting one wrong never
            counts against you; getting them right builds your mastery.
          </Typography>
        </Box>

        <Box sx={{ display: "grid", gap: 1.5 }}>
          <Box sx={{ display: "grid", gap: 0.5 }}>
            <Typography variant="overline" color="text.secondary">Length</Typography>
            <ToggleButtonGroup size="small" exclusive value={length} onChange={(_event, value) => { if (value !== null) reconfigure(() => setLength(value)); }}>
              {SESSION_LENGTHS.map((option) => (
                <ToggleButton key={option} value={option}>{option}</ToggleButton>
              ))}
              <ToggleButton value={ENDLESS}>Endless</ToggleButton>
            </ToggleButtonGroup>
          </Box>

          <Box sx={{ display: "grid", gap: 0.5 }}>
            <Typography variant="overline" color="text.secondary">Order</Typography>
            <ToggleButtonGroup size="small" exclusive value={order} onChange={(_event, value) => { if (value !== null) reconfigure(() => setOrder(value)); }}>
              {(Object.keys(ORDER_LABELS) as Order[]).map((option) => (
                <ToggleButton key={option} value={option}>{ORDER_LABELS[option]}</ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Box>

          <Box sx={{ display: "grid", gap: 0.5 }}>
            <Typography variant="overline" color="text.secondary">Questions</Typography>
            <ToggleButtonGroup size="small" exclusive value={filter} onChange={(_event, value) => { if (value !== null) reconfigure(() => setFilter(value)); }}>
              {(Object.keys(FILTER_LABELS) as Filter[]).map((option) => (
                <ToggleButton key={option} value={option}>{FILTER_LABELS[option]}</ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Box>
        </Box>

        {error ? <Alert severity="error">{error}</Alert> : null}
        <Box>
          <Button variant="contained" startIcon={<Icon name="fitness_center" />} onClick={handleStart} disabled={loading}>
            {loading ? "Loading…" : "Start practising"}
          </Button>
        </Box>
      </Paper>
    );
  }

  return (
    <Stack sx={{ gap: 1.5 }}>
      <Stack direction="row" sx={{ gap: 1, alignItems: "center", flexWrap: "wrap" }}>
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
          {answeredCount > 0 ? `${correctCount} of ${answeredCount} correct` : "Answer to see how you're doing"}
        </Typography>
        <Button size="small" variant="text" onClick={() => setStarted(false)}>Change options</Button>
      </Stack>
      {length !== ENDLESS && questions.length > 0 ? (
        <LinearProgress variant="determinate" value={Math.min((position / questions.length) * 100, 100)} />
      ) : null}

      {loading && !current ? <Typography color="text.secondary">Loading questions…</Typography> : null}
      {error ? <Alert severity="error">{error}</Alert> : null}

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
            <Button variant="outlined" onClick={handleNext} disabled={loading}>
              Next question
            </Button>
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
          ) : questions.length === 0 && filter === "unseen" ? (
            <>
              <Typography sx={{ fontWeight: 700 }}>You&apos;ve seen every question here</Typography>
              <Typography variant="body2" color="text.secondary">
                {toppedUp
                  ? "More questions are being written now — check back in a moment."
                  : "Ask for a fresh batch, or switch to “Everything” to drill the ones you've already answered."}
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
                {filter === "missed" ? "You haven't missed anything here yet." : "There are no questions in this scope yet."}
              </Typography>
            </>
          ) : (
            <>
              <Typography sx={{ fontWeight: 700 }}>Session complete</Typography>
              <Typography variant="body2" color="text.secondary">
                {correctCount} of {answeredCount} correct.
              </Typography>
            </>
          )}
          <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap" }}>
            <Button variant="outlined" onClick={handleStart} disabled={loading}>New set</Button>
            <Button variant="text" onClick={() => setStarted(false)}>Change options</Button>
          </Stack>
        </Paper>
      ) : null}
    </Stack>
  );
}
