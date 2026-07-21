"use client";

import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { CitationExcerptResponse, getCitationExcerpt } from "@/lib/api";
import { CanopyLoader } from "@/components/canopy-loader";
import { createClient } from "@/lib/supabase/client";

/** Shows the real source excerpt behind a lesson citation marker -- the "concrete, not
 * decorative" citation the product plan calls for, fetched on demand since excerpt text
 * isn't part of the lesson bundle itself. */
export function CitationExcerptDialog({
  courseId,
  citationId,
  onOpenChange,
}: {
  courseId: string;
  citationId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const [excerpt, setExcerpt] = useState<CitationExcerptResponse>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const open = citationId != null;

  useEffect(() => {
    if (!citationId) return;
    let cancelled = false;

    async function load() {
      setExcerpt(undefined);
      setError(undefined);
      setLoading(true);
      try {
        const { data } = await createClient().auth.getSession();
        if (!data.session) throw new Error("Your session has expired. Please sign in again.");
        const response = await getCitationExcerpt(courseId, citationId as string, data.session.access_token);
        if (!cancelled) setExcerpt(response);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Unable to load this source excerpt.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [courseId, citationId]);

  const meta = [excerpt?.section, excerpt?.page_number != null ? `Page ${excerpt.page_number}` : null].filter(Boolean).join(" · ");

  return (
    <Dialog open={open} onClose={() => onOpenChange(false)} fullWidth maxWidth="sm">
      <DialogTitle>{excerpt?.filename ?? "Source excerpt"}</DialogTitle>
      <DialogContent>
        <Stack sx={{ gap: 1.5, pt: 0.5 }}>
          {meta ? <Typography variant="caption" color="text.secondary">{meta}</Typography> : null}
          {loading ? <CanopyLoader label="Loading excerpt…" size={44} py={3} /> : null}
          {error ? <Alert severity="error">{error}</Alert> : null}
          {excerpt ? (
            <Box
              component="pre"
              sx={{
                m: 0,
                p: 1.5,
                borderRadius: 1.5,
                bgcolor: "action.hover",
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                fontSize: "0.85em",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                maxHeight: 360,
                overflowY: "auto"
              }}
            >
              {excerpt.content}
            </Box>
          ) : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button variant="text" onClick={() => onOpenChange(false)}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
