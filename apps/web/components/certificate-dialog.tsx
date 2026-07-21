"use client";

import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import { CertificateResponse, CourseNotCompletedError, exportCertificate, getCertificate } from "@/lib/api";
import { CertificateCard } from "@/components/certificate-card";
import { CanopyLoader } from "@/components/canopy-loader";
import { Icon } from "@/components/icon";
import { createClient } from "@/lib/supabase/client";

/** Fetches and displays the completion certificate for a course, once every lesson in
 *  it is done. Self-fetching on open, same pattern as CourseSourcesDialog. */
export function CertificateDialog({ courseId, open, onOpenChange }: { courseId: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [certificate, setCertificate] = useState<CertificateResponse>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [exporting, setExporting] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string>();

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
        const pdf = await exportCertificate(courseId, data.session.access_token);
        if (!cancelled) {
          setCertificate(response);
          setPreviewUrl(URL.createObjectURL(pdf));
        }
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

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  useEffect(() => {
    if (!linkCopied) return;
    const timer = window.setTimeout(() => setLinkCopied(false), 2000);
    return () => window.clearTimeout(timer);
  }, [linkCopied]);

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

  async function handleCopyLink() {
    if (!certificate) return;
    await navigator.clipboard.writeText(certificate.verify_url);
    setLinkCopied(true);
  }

  return (
    <Dialog open={open} onClose={() => onOpenChange(false)} fullWidth maxWidth="lg">
      <DialogContent sx={{ pt: 2 }}>
        {loading ? <CanopyLoader label="Loading certificate…" size={44} py={3} /> : null}
        {error ? <Alert severity="info">{error}</Alert> : null}
        {previewUrl ? (
          <Box sx={{ width: "100%", aspectRatio: "11 / 8.5", border: 1, borderColor: "divider", borderRadius: 1, overflow: "hidden", bgcolor: "grey.100" }}>
            <iframe title={`${certificate?.course_title ?? "Course"} certificate preview`} src={previewUrl} style={{ display: "block", width: "100%", height: "100%", border: 0 }} />
          </Box>
        ) : certificate ? <CertificateCard certificate={certificate} /> : null}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 3, flexWrap: "wrap", gap: 1 }}>
        {certificate ? (
          <Button
            variant="text"
            startIcon={<Icon name={linkCopied ? "check" : "link"} />}
            onClick={() => void handleCopyLink()}
          >
            {linkCopied ? "Link copied" : "Copy verify link"}
          </Button>
        ) : null}
        <Box sx={{ flex: 1 }} />
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
