"use client";

import { FormEvent, useState } from "react";
import Box from "@mui/material/Box";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Alert from "@mui/material/Alert";
import Slider from "@mui/material/Slider";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
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
  const [lessonMin, setLessonMin] = useState(course.lesson_min);
  const [lessonMax, setLessonMax] = useState(course.lesson_max);
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
      setLessonMin(course.lesson_min);
      setLessonMax(course.lesson_max);
      setError(undefined);
    }
  }

  // Base UI's Slider had `minStepsBetweenValues={1}` to keep the two thumbs from
  // colliding; MUI's Slider has no direct equivalent, so clamp here instead (same
  // approach as the create-course form's lesson-range slider).
  function handleLessonRangeChange(_event: Event, value: number | number[]) {
    if (!Array.isArray(value)) return;
    const [min, max] = value;
    setLessonMin(Math.min(min, max - 1));
    setLessonMax(Math.max(max, min + 1));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(undefined);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const updated = await updateCourse(
        course.id,
        { title, quiz_max_attempts: quizMaxAttempts, lesson_min: lessonMin, lesson_max: lessonMax },
        data.session.access_token
      );
      onSaved(updated);
      onOpenChange(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save course settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onClose={() => onOpenChange(false)} fullWidth maxWidth="xs">
      <DialogTitle>Course settings</DialogTitle>
      <form onSubmit={handleSubmit}>
        <DialogContent>
          <Stack sx={{ gap: 2.5, pt: 0.5 }}>
            <TextField
              label="Course title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
              autoFocus
              fullWidth
            />
            <TextField
              label="Quiz attempts per question"
              type="number"
              slotProps={{ htmlInput: { min: 1, max: 10 } }}
              value={quizMaxAttempts}
              onChange={(event) => setQuizMaxAttempts(Math.max(1, Math.min(10, Number(event.target.value) || 1)))}
              fullWidth
            />
            <Box>
              <Typography gutterBottom>
                Activity range <Typography component="span" sx={{ fontWeight: 700 }}>{lessonMin}–{lessonMax} activities</Typography>
              </Typography>
              <Slider
                value={[lessonMin, lessonMax]}
                onChange={handleLessonRangeChange}
                min={6}
                max={24}
                step={1}
                disableSwap
                getAriaLabel={(index) => (index === 0 ? "Minimum lessons" : "Maximum lessons")}
              />
              <Typography variant="caption" color="text.secondary">
                Takes effect the next time you regenerate this course. It won&apos;t retroactively add or remove lessons that already exist.
              </Typography>
            </Box>
            {error ? <Alert severity="error">{error}</Alert> : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button variant="text" onClick={() => onOpenChange(false)} disabled={saving}>Cancel</Button>
          <Button variant="contained" type="submit" disabled={saving}>{saving ? "Saving…" : "Save"}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
