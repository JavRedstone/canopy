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
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
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
      <DialogTitle>Source documents</DialogTitle>
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
            <List disablePadding sx={{ display: "grid", gap: 1 }}>
              {sources.map((source) => {
                const downloadable = source.status !== "uploading" && source.status !== "failed";
                return (
                  <ListItemButton
                    key={source.id}
                    onClick={() => void handleDownload(source)}
                    disabled={!downloadable || downloadingId === source.id}
                    sx={{ border: 1, borderColor: "divider", borderRadius: 1.5 }}
                  >
                    <ListItemIcon sx={{ minWidth: 40 }}>
                      <Icon name={sourceIcon(source.mime_type)} />
                    </ListItemIcon>
                    <ListItemText primary={source.filename} secondary={formatBytes(source.byte_size)} />
                    {downloadingId === source.id ? (
                      <CircularProgress size={18} />
                    ) : (
                      <Chip size="small" label={STATUS_LABEL[source.status]} variant="outlined" color={source.status === "failed" ? "error" : "default"} />
                    )}
                  </ListItemButton>
                );
              })}
            </List>
          ) : null}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button variant="text" onClick={() => onOpenChange(false)}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
