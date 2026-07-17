"use client";

import { useState } from "react";
import { QuizAnswerRequest, QuizGradeResponse, QuizItemPreview, answerQuizItem } from "@/lib/api";
import { MarkdownText } from "@/components/markdown-text";
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

  function handleRetry() {
    setSelected([]);
    setText("");
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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to grade your answer.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="quiz-question" data-answered={answered || undefined} data-correct={grade?.correct || undefined}>
      <div className="quiz-question-header">
        <span className="quiz-question-number">{index + 1}</span>
        <MarkdownText>{item.prompt_markdown}</MarkdownText>
      </div>

      {isChoice ? (
        <div className="quiz-options" role="group">
          {item.options.map((option, optionIndex) => {
            const optionGrade = grade?.options[optionIndex];
            const isSelected = selected.includes(optionIndex);
            return (
              <label
                className="quiz-option"
                data-selected={isSelected || undefined}
                data-correct={optionGrade?.correct || undefined}
                data-incorrect={answered && isSelected && optionGrade && !optionGrade.correct ? true : undefined}
                key={optionIndex}
              >
                <input
                  type={item.kind === "mcq" ? "radio" : "checkbox"}
                  name={`quiz-${item.id}`}
                  checked={isSelected}
                  disabled={answered || exhausted}
                  onChange={() => toggleOption(optionIndex)}
                />
                <span className="quiz-option-body">
                  <span>{option.text}</span>
                  {answered && optionGrade && (isSelected || optionGrade.correct) ? (
                    <span className="quiz-option-explanation muted">{optionGrade.explanation_markdown}</span>
                  ) : null}
                </span>
              </label>
            );
          })}
          {item.kind === "multi_select" ? <p className="muted quiz-kind-note">Select every answer that applies.</p> : null}
        </div>
      ) : item.kind === "fill" ? (
        <input
          className="quiz-text-input"
          type="text"
          value={text}
          placeholder="Your answer"
          disabled={answered || exhausted}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") void handleSubmit(); }}
        />
      ) : (
        <textarea
          className="quiz-text-input quiz-textarea"
          rows={4}
          value={text}
          placeholder="Write a short answer in your own words…"
          disabled={answered || exhausted}
          onChange={(event) => setText(event.target.value)}
        />
      )}

      {error ? <p className="error">{error}</p> : null}

      {exhausted ? (
        <p className="muted">No attempts remaining.</p>
      ) : !answered ? (
        <div className="quiz-actions">
          <button className="button button-secondary" type="button" onClick={handleSubmit} disabled={!answer || submitting}>
            {submitting ? "Checking…" : "Check answer"}
          </button>
        </div>
      ) : (
        <div className={`quiz-result ${grade.correct ? "passed" : "failed"}`}>
          <strong>{grade.correct ? "Correct" : "Not quite"}</strong>
          {grade.feedback_markdown ? <MarkdownText>{grade.feedback_markdown}</MarkdownText> : null}
          {!grade.correct && grade.correct_answers.length > 0 ? (
            <p>Accepted answer{grade.correct_answers.length > 1 ? "s" : ""}: {grade.correct_answers.join(", ")}</p>
          ) : null}
          <MarkdownText>{grade.explanation_markdown}</MarkdownText>
          {!grade.correct ? (
            canRetry ? (
              <div className="quiz-actions">
                <button className="button button-secondary" type="button" onClick={handleRetry}>
                  Try again ({attemptsRemaining} attempt{attemptsRemaining === 1 ? "" : "s"} left)
                </button>
              </div>
            ) : (
              <p className="muted">No attempts remaining.</p>
            )
          ) : null}
        </div>
      )}
    </div>
  );
}

export function QuizSection({ courseId, slug, items, maxAttempts = DEFAULT_MAX_ATTEMPTS }: { courseId: string; slug: string; items?: QuizItemPreview[]; maxAttempts?: number }) {
  if (!items?.length) return null;
  return (
    <section className="quiz-section">
      <div className="lesson-content-divider"><span>Mastery check</span></div>
      <p className="muted quiz-mastery-note">Up to {maxAttempts} attempts per question: show what you&apos;ve learned.</p>
      {items.map((item, index) => (
        <QuizQuestion courseId={courseId} slug={slug} item={item} index={index} maxAttempts={maxAttempts} key={item.id} />
      ))}
    </section>
  );
}
