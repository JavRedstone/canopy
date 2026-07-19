"use client";

import { useState } from "react";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Alert from "@mui/material/Alert";
import Stack from "@mui/material/Stack";
import Switch from "@mui/material/Switch";
import Typography from "@mui/material/Typography";
import InputAdornment from "@mui/material/InputAdornment";
import CircularProgress from "@mui/material/CircularProgress";
import { CourseSummary, updateCourse } from "@/lib/api";
import { Icon } from "@/components/icon";
import { createClient } from "@/lib/supabase/client";

export function CourseShareDialog({
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
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [copied, setCopied] = useState(false);

  // Anyone with this link lands on the library with the import dialog pre-filled.
  const shareLink =
    typeof window !== "undefined" ? `${window.location.origin}/courses?import=${course.id}` : "";

  async function setShared(next: boolean) {
    setSaving(true);
    setError(undefined);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const updated = await updateCourse(course.id, { is_shared: next }, data.session.access_token);
      onSaved(updated);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update sharing.");
    } finally {
      setSaving(false);
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(shareLink);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setError("Could not copy the link. Copy it manually instead.");
    }
  }

  return (
    <Dialog open={open} onClose={() => onOpenChange(false)} fullWidth maxWidth="xs">
      <DialogTitle>Share “{course.title}”</DialogTitle>
      <DialogContent>
        <Stack sx={{ gap: 2, pt: 0.5 }}>
          <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", gap: 2 }}>
            <Stack sx={{ minWidth: 0 }}>
              <Typography sx={{ fontWeight: 600 }}>Anyone with the link</Typography>
              <Typography variant="caption" color="text.secondary">
                {course.is_shared
                  ? "Anyone with the link can import their own copy of this course."
                  : "Only you can see this course. Turn on to let others import a copy."}
              </Typography>
            </Stack>
            <Switch
              checked={course.is_shared}
              onChange={(event) => void setShared(event.target.checked)}
              disabled={saving}
              slotProps={{ input: { "aria-label": "Anyone with the link can import" } }}
            />
          </Stack>

          {saving ? (
            <Stack direction="row" sx={{ alignItems: "center", gap: 1, color: "text.secondary" }}>
              <CircularProgress size={16} /> <Typography variant="caption">Updating…</Typography>
            </Stack>
          ) : null}

          {course.is_shared ? (
            <TextField
              label="Share link"
              value={shareLink}
              fullWidth
              size="small"
              slotProps={{
                input: {
                  readOnly: true,
                  endAdornment: (
                    <InputAdornment position="end">
                      <Button
                        size="small"
                        onClick={() => void copyLink()}
                        startIcon={<Icon name={copied ? "check" : "content_copy"} />}
                      >
                        {copied ? "Copied" : "Copy"}
                      </Button>
                    </InputAdornment>
                  ),
                },
              }}
              onFocus={(event) => event.target.select()}
            />
          ) : null}

          <Typography variant="caption" color="text.secondary">
            Sharing copies the course content only — your progress, mastery, and points stay private.
          </Typography>

          {error ? <Alert severity="error">{error}</Alert> : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button variant="contained" onClick={() => onOpenChange(false)}>Done</Button>
      </DialogActions>
    </Dialog>
  );
}
