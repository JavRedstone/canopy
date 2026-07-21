"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";
import TextField from "@mui/material/TextField";
import Alert from "@mui/material/Alert";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import CircularProgress from "@mui/material/CircularProgress";
import { importCourse, SharedCourseNotFoundError } from "@/lib/api";
import { Icon } from "@/components/icon";
import { createClient } from "@/lib/supabase/client";

const UUID_PATTERN = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

// Accept either a raw course id or a pasted share link (…/courses?import=<id>).
function extractCourseId(input: string): string | null {
  const match = input.trim().match(UUID_PATTERN);
  return match ? match[0] : null;
}

export function ImportCourseButton() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string>();

  // A share link lands here as /courses?import=<id> -- open the dialog pre-filled so the
  // recipient just confirms. Read from the URL directly to avoid a Suspense boundary, and
  // do it post-mount (not a lazy initializer) so the server and first client render agree.
  useEffect(() => {
    const fromLink = new URLSearchParams(window.location.search).get("import");
    if (!fromLink) return;
    /* eslint-disable react-hooks/set-state-in-effect -- one-shot sync from the share-link URL param on mount */
    setValue(fromLink);
    setOpen(true);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  async function handleImport() {
    const courseId = extractCourseId(value);
    if (!courseId) {
      setError("Paste a valid course ID or share link.");
      return;
    }
    setImporting(true);
    setError(undefined);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const course = await importCourse(courseId, data.session.access_token);
      router.push(`/courses/${course.id}`);
    } catch (caught) {
      if (caught instanceof SharedCourseNotFoundError) {
        setError("No shared course was found for that ID. Ask the owner to turn on sharing, then double-check the ID.");
      } else {
        setError(caught instanceof Error ? caught.message : "Unable to import the course.");
      }
      setImporting(false);
    }
  }

  return (
    <>
      <Button variant="outlined" startIcon={<Icon name="download" />} onClick={() => setOpen(true)}>
        Import
      </Button>
      <Dialog
        open={open}
        onClose={() => {
          if (!importing) setOpen(false);
        }}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>Import a shared course</DialogTitle>
        <DialogContent>
          <Stack sx={{ gap: 1.5, pt: 0.5 }}>
            <Typography variant="body2" color="text.secondary">
              Paste a course ID or share link. You&apos;ll get your own copy of its content (lessons, quizzes, and labs), starting from fresh progress.
            </Typography>
            <TextField
              label="Course ID or share link"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              autoFocus
              fullWidth
              placeholder="e.g. 3f2b8c…  or  https://…/courses?import=…"
              onKeyDown={(event) => {
                if (event.key === "Enter") void handleImport();
              }}
            />
            {error ? <Alert severity="error">{error}</Alert> : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button variant="text" onClick={() => setOpen(false)} disabled={importing}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => void handleImport()}
            disabled={importing || !value.trim()}
            startIcon={importing ? <CircularProgress size={16} /> : undefined}
          >
            {importing ? "Importing…" : "Import"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
