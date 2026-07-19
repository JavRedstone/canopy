"use client";

import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { CertificateResponse, CourseNotCompletedError, exportCertificate, getCertificate } from "@/lib/api";
import { Icon } from "@/components/icon";
import { createClient } from "@/lib/supabase/client";

/** Fetches and displays the completion certificate for a course, once every lesson in
 *  it is done. Self-fetching on open, same pattern as CourseSourcesDialog. */
export function CertificateDialog({ courseId, open, onOpenChange }: { courseId: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [certificate, setCertificate] = useState<CertificateResponse>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(undefined);
      try {
        const { data } = await createClient().auth.getSession();
        if (!data.session) throw new Error("Your session has expired. Please sign in again.");
        const response = await getCertificate(courseId, data.session.access_token);
        if (!cancelled) setCertificate(response);
      } catch (caught) {
        if (cancelled) return;
        setError(
          caught instanceof CourseNotCompletedError
            ? "Complete every lesson in this course to unlock your certificate."
            : caught instanceof Error
              ? caught.message
              : "Unable to load the certificate."
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [courseId, open]);

  async function handleDownload() {
    if (!certificate) return;
    setExporting(true);
    setError(undefined);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const pdf = await exportCertificate(courseId, data.session.access_token);
      const url = URL.createObjectURL(pdf);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${certificate.course_title.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "course"}-certificate.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to download the certificate.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <Dialog open={open} onClose={() => onOpenChange(false)} fullWidth maxWidth="sm">
      <DialogContent sx={{ pt: 4 }}>
        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
            <CircularProgress size={28} />
          </Box>
        ) : null}
        {error ? <Alert severity="info">{error}</Alert> : null}
        {certificate ? (
          <Box
            sx={{
              position: "relative", p: { xs: 3, sm: 4 }, borderRadius: 3, textAlign: "center",
              background: "linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%)",
              border: "2px solid #a5b4fc", boxShadow: "0 18px 40px rgba(49, 46, 129, 0.15)"
            }}
          >
            <Box sx={{ position: "absolute", inset: 8, border: "1px solid #c7d2fe", borderRadius: 2, pointerEvents: "none" }} />
            <Stack sx={{ alignItems: "center", gap: 1.25 }}>
              <Box sx={{ width: 56, height: 56, borderRadius: "50%", display: "grid", placeItems: "center", bgcolor: "#312e81", color: "white" }}>
                <Icon name="workspace_premium" />
              </Box>
              <Typography variant="overline" sx={{ letterSpacing: "0.13em", fontWeight: 700, color: "#6366f1" }}>Certificate of completion</Typography>
              <Typography variant="body2" color="text.secondary">This certifies that</Typography>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>{certificate.learner_email}</Typography>
              <Typography variant="body2" color="text.secondary">has successfully completed</Typography>
              <Typography variant="h5" sx={{ fontWeight: 800, color: "#312e81", letterSpacing: "-0.02em" }}>{certificate.course_title}</Typography>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                Issued {new Date(certificate.issued_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })} · Certificate ID {certificate.certificate_id}
              </Typography>
            </Stack>
          </Box>
        ) : null}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Button variant="text" onClick={() => onOpenChange(false)}>Close</Button>
        {certificate ? (
          <Button
            variant="contained"
            startIcon={exporting ? <CircularProgress size={16} sx={{ color: "inherit" }} /> : <Icon name="download" />}
            onClick={() => void handleDownload()}
            disabled={exporting}
          >
            {exporting ? "Preparing PDF…" : "Download PDF"}
          </Button>
        ) : null}
      </DialogActions>
    </Dialog>
  );
}
