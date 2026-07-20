"use client";

import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import { BrandLink } from "@/components/brand-link";
import { CertificateCard } from "@/components/certificate-card";
import { Icon } from "@/components/icon";
import { CertificateResponse, exportPublicCertificate, getPublicCertificate } from "@/lib/api";

/** The durable, no-auth landing page a shared certificate link opens to -- anyone with
 *  the link can view and verify it, the same trust model course-sharing links already use. */
export function PublicCertificateView({ certificateId }: { certificateId: string }) {
  const [certificate, setCertificate] = useState<CertificateResponse>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getPublicCertificate(certificateId)
      .then((response) => {
        if (!cancelled) setCertificate(response);
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Unable to load this certificate.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [certificateId]);

  async function handleDownload() {
    setExporting(true);
    try {
      const pdf = await exportPublicCertificate(certificateId);
      const url = URL.createObjectURL(pdf);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${(certificate?.course_title ?? "course").replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "")}-certificate.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  return (
    <Box sx={{ mt: 1 }}>
      <BrandLink />
      <Box sx={{ mt: 4 }}>
        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
            <CircularProgress size={28} />
          </Box>
        ) : null}
        {error ? <Alert severity="error">{error}</Alert> : null}
        {certificate ? (
          <>
            <CertificateCard certificate={certificate} />
            <Box sx={{ display: "flex", justifyContent: "center", mt: 3 }}>
              <Button
                variant="contained"
                startIcon={exporting ? <CircularProgress size={16} sx={{ color: "inherit" }} /> : <Icon name="download" />}
                onClick={() => void handleDownload()}
                disabled={exporting}
              >
                {exporting ? "Preparing PDF…" : "Download PDF"}
              </Button>
            </Box>
          </>
        ) : null}
      </Box>
    </Box>
  );
}
