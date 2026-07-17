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

export function QuizQuestion({ courseId, slug, item, index, retryable }: { courseId: string; slug: string; item: QuizItemPreview; index: number; retryable?: boolean }) {
  const [selected, setSelected] = useState<number[]>([]);
  const [text, setText] = useState("");
  const [grade, setGrade] = useState<QuizGradeResponse>();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>();

  function handleRetry() {
    setSelected([]);
    setText("");
    setGrade(undefined);
    setError(undefined);
  }

  const answered = grade !== undefined;
  const answer = answerFor(item, selected, text);
  const isChoice = item.kind === "mcq" || item.kind === "multi_select";

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
      setGrade(await answerQuizItem(courseId, slug, item.id, answer, data.session.access_token));
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
                  disabled={answered}
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
          disabled={answered}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") void handleSubmit(); }}
        />
      ) : (
        <textarea
          className="quiz-text-input quiz-textarea"
          rows={4}
          value={text}
          placeholder="Write a short answer in your own words…"
          disabled={answered}
          onChange={(event) => setText(event.target.value)}
        />
      )}

      {error ? <p className="error">{error}</p> : null}

      {!answered ? (
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
          {retryable && !grade.correct ? (
            <div className="quiz-actions">
              <button className="button button-secondary" type="button" onClick={handleRetry}>Try again</button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

export function QuizSection({ courseId, slug, items }: { courseId: string; slug: string; items?: QuizItemPreview[] }) {
  if (!items?.length) return null;
  return (
    <section className="quiz-section">
      <div className="lesson-content-divider"><span>Mastery check</span></div>
      <p className="muted quiz-mastery-note">One attempt per question — show what you&apos;ve learned.</p>
      {items.map((item, index) => (
        <QuizQuestion courseId={courseId} slug={slug} item={item} index={index} key={item.id} />
      ))}
    </section>
  );
}
