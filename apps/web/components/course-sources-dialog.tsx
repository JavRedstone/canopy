"use client";

import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import List from "@mui/material/List";
import ListItemText from "@mui/material/ListItemText";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { CourseSourceSummary, getCourseSources, getSourceDownloadUrl } from "@/lib/api";
import { Icon } from "@/components/icon";
import { createClient } from "@/lib/supabase/client";

function formatBytes(byteSize: number): string {
  if (byteSize < 1024) return `${byteSize} B`;
  if (byteSize < 1024 * 1024) return `${(byteSize / 1024).toFixed(1)} KB`;
  return `${(byteSize / (1024 * 1024)).toFixed(1)} MB`;
}

function sourceIcon(mimeType: string): string {
  return mimeType === "application/pdf" ? "picture_as_pdf" : "description";
}

const STATUS_LABEL: Record<CourseSourceSummary["status"], string> = {
  uploading: "Uploading…",
  uploaded: "Queued",
  ingesting: "Processing…",
  ready: "Ready",
  failed: "Failed",
};

/** Lets a learner download the original documents a course was built from -- the same
 *  files behind the small citation excerpts shown inline in lessons, but the whole thing. */
export function CourseSourcesDialog({ courseId, open, onOpenChange }: { courseId: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [sources, setSources] = useState<CourseSourceSummary[]>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [downloadingId, setDownloadingId] = useState<string>();

  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(undefined);
      try {
        const { data } = await createClient().auth.getSession();
        if (!data.session) throw new Error("Your session has expired. Please sign in again.");
        const response = await getCourseSources(courseId, data.session.access_token);
        if (!cancelled) setSources(response);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Unable to load this course's sources.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [courseId, open]);

  async function handleDownload(source: CourseSourceSummary) {
    setDownloadingId(source.id);
    setError(undefined);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const { download_url } = await getSourceDownloadUrl(courseId, source.id, data.session.access_token);
      window.open(download_url, "_blank", "noopener,noreferrer");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to download this source.");
    } finally {
      setDownloadingId(undefined);
    }
  }

  return (
    <Dialog open={open} onClose={() => onOpenChange(false)} fullWidth maxWidth="sm">
      <DialogTitle sx={{ pb: 1 }}>Source library</DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 0.5 }}>
          {loading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
              <CircularProgress size={28} />
            </Box>
          ) : null}
          {error ? <Alert severity="error" sx={{ mb: 1.5 }}>{error}</Alert> : null}
          {!loading && sources && sources.length === 0 ? (
            <Typography color="text.secondary">This course has no attached source documents.</Typography>
          ) : null}
          {sources && sources.length > 0 ? (
            <>
              <Box sx={{ mb: 2, p: 1.5, borderRadius: 2, border: 1, borderColor: "divider", bgcolor: "action.hover" }}>
                <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", gap: 2 }}>
                  <Box>
                    <Typography sx={{ fontWeight: 700 }}>Course materials</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>Original documents used to create this coursebook.</Typography>
                  </Box>
                  <Box sx={{ minWidth: 40, height: 40, borderRadius: 1.5, display: "grid", placeItems: "center", color: "primary.main", bgcolor: "rgba(99,102,241,0.10)" }}>
                    <Icon name="folder_open" />
                  </Box>
                </Stack>
              </Box>
              <List disablePadding sx={{ display: "grid", gap: 1.2 }}>
              {sources.map((source) => {
                const downloadable = source.status !== "uploading" && source.status !== "failed";
                return (
                  <Box
                    key={source.id}
                    sx={{ border: 1, borderColor: "divider", borderRadius: 1.5, p: 1.25, bgcolor: "background.paper", "&:hover": downloadable ? { bgcolor: "action.hover" } : {} }}
                  >
                    <Stack direction="row" sx={{ alignItems: "center", gap: 1.3 }}>
                      <Box sx={{ width: 44, height: 52, borderRadius: 1.25, display: "grid", placeItems: "center", color: source.mime_type === "application/pdf" ? "#dc2626" : "#4338ca", bgcolor: source.mime_type === "application/pdf" ? "#fef2f2" : "#eef2ff" }}>
                        <Icon name={sourceIcon(source.mime_type)} />
                      </Box>
                      <ListItemText
                        primary={<Typography noWrap sx={{ fontWeight: 700 }}>{source.filename}</Typography>}
                        secondary={`Source ${String(source.position).padStart(2, "0")} · ${formatBytes(source.byte_size)}`}
                      />
                      <Stack sx={{ alignItems: "flex-end", gap: 0.75, flexShrink: 0 }}>
                        <Chip size="small" label={STATUS_LABEL[source.status]} variant="outlined" color={source.status === "failed" ? "error" : "default"} />
                        <Button size="small" startIcon={downloadingId === source.id ? <CircularProgress size={13} /> : <Icon name="download" />} onClick={() => void handleDownload(source)} disabled={!downloadable || downloadingId === source.id}>
                          Download
                        </Button>
                      </Stack>
                    </Stack>
                  </Box>
                );
              })}
              </List>
            </>
          ) : null}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button variant="text" onClick={() => onOpenChange(false)}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
