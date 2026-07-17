"use client";

import { Dialog } from "@base-ui/react/dialog";
import { FormEvent, useState } from "react";
import { CourseSummary, updateCourse } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

export function CourseSettingsDialog({
  course,
  open,
  onOpenChange,
  onSaved,
}: {
  course: CourseSummary;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (course: CourseSummary) => void;
}) {
  const [title, setTitle] = useState(course.title);
  const [quizMaxAttempts, setQuizMaxAttempts] = useState(course.quiz_max_attempts);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  // Re-seed the form fields from the latest course whenever the dialog transitions to
  // open, without an effect: comparing against the previous `open` value during render
  // (React's "adjusting state during render" pattern) avoids the extra render an effect
  // would cause.
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setTitle(course.title);
      setQuizMaxAttempts(course.quiz_max_attempts);
      setError(undefined);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(undefined);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const updated = await updateCourse(course.id, { title, quiz_max_attempts: quizMaxAttempts }, data.session.access_token);
      onSaved(updated);
      onOpenChange(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save course settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="dialog-backdrop" />
        <Dialog.Popup className="dialog-popup">
          <Dialog.Title className="dialog-title">Course settings</Dialog.Title>
          <form className="form" onSubmit={handleSubmit}>
            <label className="field" htmlFor="course-settings-title">
              Course title
              <input className="input" id="course-settings-title" value={title} onChange={(event) => setTitle(event.target.value)} required />
            </label>
            <label className="field" htmlFor="course-settings-attempts">
              Quiz attempts per question
              <input
                className="input"
                id="course-settings-attempts"
                type="number"
                min={1}
                max={10}
                value={quizMaxAttempts}
                onChange={(event) => setQuizMaxAttempts(Math.max(1, Math.min(10, Number(event.target.value) || 1)))}
              />
            </label>
            {error ? <p className="error">{error}</p> : null}
            <div className="dialog-actions">
              <button className="button button-secondary" type="button" onClick={() => onOpenChange(false)} disabled={saving}>Cancel</button>
              <button className="button" type="submit" disabled={saving}>{saving ? "Saving…" : "Save"}</button>
            </div>
          </form>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
