"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Paper from "@mui/material/Paper";
import Radio from "@mui/material/Radio";
import Checkbox from "@mui/material/Checkbox";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Alert from "@mui/material/Alert";
import Avatar from "@mui/material/Avatar";
import Divider from "@mui/material/Divider";
import { alpha } from "@mui/material/styles";
import { QuizAnswerRequest, QuizGradeResponse, QuizItemPreview, answerQuizItem } from "@/lib/api";
import { MarkdownText } from "@/components/markdown-text";
import { ConfettiBurst } from "@/components/confetti-burst";
import { createClient } from "@/lib/supabase/client";

function answerFor(item: QuizItemPreview, selected: number[], text: string): QuizAnswerRequest | null {
  if (item.kind === "mcq") return selected.length === 1 ? { selected_option_index: selected[0] } : null;
  if (item.kind === "multi_select") return selected.length > 0 ? { selected_option_indices: selected } : null;
  return text.trim() ? { answer_text: text } : null;
}

const DEFAULT_MAX_ATTEMPTS = 3;

function selectionFromAnswer(answer: QuizAnswerRequest | null): number[] {
  if (!answer) return [];
  if (answer.selected_option_index !== undefined && answer.selected_option_index !== null) return [answer.selected_option_index];
  return answer.selected_option_indices ?? [];
}

export function QuizQuestion({ courseId, slug, item, index, maxAttempts = DEFAULT_MAX_ATTEMPTS }: { courseId: string; slug: string; item: QuizItemPreview; index: number; maxAttempts?: number }) {
  // A previously-correct item is hydrated with the exact answer and grade it was given
  // last time, so it replays as the real answered state instead of resetting blank.
  const [selected, setSelected] = useState<number[]>(() => selectionFromAnswer(item.previous_answer));
  const [text, setText] = useState(item.previous_answer?.answer_text ?? "");
  const [grade, setGrade] = useState<QuizGradeResponse | undefined>(item.previous_grade ?? undefined);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>();
  const [attemptsUsed, setAttemptsUsed] = useState(item.attempts_used);
  // Only fresh, just-submitted correct answers celebrate -- not ones hydrated from a
  // previous session, which would confetti-spam every page load.
  const [celebrateNonce, setCelebrateNonce] = useState(0);

  function handleRetry() {
    // Clear choice selections (naturally re-picked), but leave any typed text answer in
    // place so a retry is an edit, not a re-type from scratch.
    setSelected([]);
    setGrade(undefined);
    setError(undefined);
  }

  const answered = grade !== undefined;
  const answer = answerFor(item, selected, text);
  const isChoice = item.kind === "mcq" || item.kind === "multi_select";
  const attemptsRemaining = answered ? grade.attempts_remaining : Math.max(maxAttempts - attemptsUsed, 0);
  const exhausted = !answered && attemptsRemaining <= 0;
  const canRetry = answered && !grade.correct && attemptsRemaining > 0;

  function toggleOption(optionIndex: number) {
    if (answered) return;
    if (item.kind === "mcq") {
      setSelected([optionIndex]);
    } else {
      setSelected((current) =>
        current.includes(optionIndex) ? current.filter((entry) => entry !== optionIndex) : [...current, optionIndex].sort((a, b) => a - b)
      );
    }
  }

  async function handleSubmit() {
    if (!answer) return;
    setSubmitting(true);
    setError(undefined);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const result = await answerQuizItem(courseId, slug, item.id, answer, data.session.access_token);
      setGrade(result);
      setAttemptsUsed(result.attempts_used);
      if (result.correct) setCelebrateNonce((current) => current + 1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to grade your answer.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        position: "relative",
        p: 2,
        display: "grid",
        gap: 1.5,
        borderLeft: answered ? 3 : 1,
        borderLeftColor: answered ? (grade.correct ? "success.main" : "error.main") : "divider"
      }}
    >
      {celebrateNonce > 0 ? <ConfettiBurst key={celebrateNonce} /> : null}
      <Stack direction="row" sx={{ gap: 1.25, alignItems: "baseline" }}>
        <Avatar sx={{ width: 22, height: 22, fontSize: "0.78rem", fontWeight: 700, bgcolor: "action.hover", color: "text.primary" }}>
          {index + 1}
        </Avatar>
        <Box sx={{ flex: 1 }}><MarkdownText>{item.prompt_markdown}</MarkdownText></Box>
      </Stack>

      {isChoice ? (
        <Stack role="group" sx={{ gap: 0.75 }}>
          {item.options.map((option, optionIndex) => {
            const optionGrade = grade?.options[optionIndex];
            const isSelected = selected.includes(optionIndex);
            const isIncorrect = Boolean(answered && isSelected && optionGrade && !optionGrade.correct);
            // Only reveal correctness for options the learner actually picked -- marking an
            // unselected option green would give away an answer they never chose.
            const isCorrect = Boolean(isSelected && optionGrade?.correct);
            return (
              <Paper
                key={optionIndex}
                variant="outlined"
                component="label"
                sx={{
                  display: "flex",
                  gap: 1.25,
                  alignItems: "flex-start",
                  p: "6px 10px",
                  cursor: answered || exhausted ? "default" : "pointer",
                  borderColor: isCorrect ? "success.main" : isIncorrect ? "error.main" : isSelected ? "text.primary" : "divider",
                  bgcolor: (theme) =>
                    isCorrect
                      ? alpha(theme.palette.success.main, 0.08)
                      : isIncorrect
                        ? alpha(theme.palette.error.main, 0.08)
                        : "transparent"
                }}
              >
                {item.kind === "mcq" ? (
                  <Radio
                    checked={isSelected}
                    disabled={answered || exhausted}
                    onChange={() => toggleOption(optionIndex)}
                    size="small"
                    sx={{ p: 0, mt: "2px" }}
                  />
                ) : (
                  <Checkbox
                    checked={isSelected}
                    disabled={answered || exhausted}
                    onChange={() => toggleOption(optionIndex)}
                    size="small"
                    sx={{ p: 0, mt: "2px" }}
                  />
                )}
                <Box sx={{ display: "grid", gap: 0.5 }}>
                  <Typography variant="body2">{option.text}</Typography>
                  {answered && optionGrade && isSelected ? (
                    <Typography variant="caption" color="text.secondary">{optionGrade.explanation_markdown}</Typography>
                  ) : null}
                </Box>
              </Paper>
            );
          })}
          {item.kind === "multi_select" ? <Typography variant="body2" color="text.secondary">Select every answer that applies.</Typography> : null}
        </Stack>
      ) : item.kind === "fill" ? (
        <TextField
          size="small"
          placeholder="Your answer"
          value={text}
          disabled={answered || exhausted}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") void handleSubmit(); }}
        />
      ) : (
        <TextField
          multiline
          rows={4}
          placeholder="Write a short answer in your own words…"
          value={text}
          disabled={answered || exhausted}
          onChange={(event) => setText(event.target.value)}
        />
      )}

      {error ? <Alert severity="error">{error}</Alert> : null}

      {exhausted ? (
        <Typography color="text.secondary">No attempts remaining.</Typography>
      ) : !answered ? (
        <Box>
          <Button variant="outlined" onClick={handleSubmit} disabled={!answer || submitting}>
            {submitting ? "Checking…" : "Check answer"}
          </Button>
        </Box>
      ) : (
        <AnimatePresence>
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
            <Alert severity={grade.correct ? "success" : "error"} sx={{ display: "grid", gap: 1 }}>
              <Typography sx={{ fontWeight: 700 }}>{grade.correct ? "Correct" : "Not quite"}</Typography>
              {grade.feedback_markdown ? <MarkdownText>{grade.feedback_markdown}</MarkdownText> : null}
              {!grade.correct && grade.correct_answers.length > 0 ? (
                <Typography variant="body2">Accepted answer{grade.correct_answers.length > 1 ? "s" : ""}: {grade.correct_answers.join(", ")}</Typography>
              ) : null}
              <MarkdownText>{grade.explanation_markdown}</MarkdownText>
              {!grade.correct ? (
                canRetry ? (
                  <Box>
                    <Button variant="outlined" size="small" onClick={handleRetry}>
                      Try again ({attemptsRemaining} attempt{attemptsRemaining === 1 ? "" : "s"} left)
                    </Button>
                  </Box>
                ) : (
                  <Typography color="text.secondary">No attempts remaining.</Typography>
                )
              ) : null}
            </Alert>
          </motion.div>
        </AnimatePresence>
      )}
    </Paper>
  );
}

export function QuizSection({ courseId, slug, items, maxAttempts = DEFAULT_MAX_ATTEMPTS }: { courseId: string; slug: string; items?: QuizItemPreview[]; maxAttempts?: number }) {
  if (!items?.length) return null;
  return (
    <Stack component="section" sx={{ gap: 2 }}>
      <Divider textAlign="left">
        <Typography variant="overline" color="text.secondary">Mastery check</Typography>
      </Divider>
      <Typography variant="body2" color="text.secondary" sx={{ mt: -1 }}>
        Use up to <Box component="strong" sx={{ fontWeight: 700, color: "text.primary" }}>{maxAttempts}</Box>{" "}attempts per question to show what you&apos;ve learned.
      </Typography>
      {items.map((item, index) => (
        <QuizQuestion courseId={courseId} slug={slug} item={item} index={index} maxAttempts={maxAttempts} key={item.id} />
      ))}
    </Stack>
  );
}
