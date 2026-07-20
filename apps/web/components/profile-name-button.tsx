"use client";

import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import TextField from "@mui/material/TextField";
import { getProfile, updateProfile } from "@/lib/api";
import { Icon } from "@/components/icon";
import { createClient } from "@/lib/supabase/client";

/** Shows the learner's display name (falling back to their email) in the header, with a
 *  click-to-edit affordance -- the only place a name can be set, since sign-in is
 *  passwordless magic-link email and never collects one. Used to personalize things like
 *  the completion certificate instead of showing a bare email address. */
export function ProfileNameButton({ email }: { email: string }) {
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    let cancelled = false;
    createClient()
      .auth.getSession()
      .then(({ data }) => {
        if (!data.session) return null;
        return getProfile(data.session.access_token);
      })
      .then((profile) => {
        if (!cancelled && profile) setDisplayName(profile.display_name);
      })
      .catch(() => {
        // Non-fatal: the header just falls back to the email already being shown.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleOpen() {
    setDraft(displayName ?? "");
    setError(undefined);
    setOpen(true);
  }

  async function handleSave() {
    setSaving(true);
    setError(undefined);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const profile = await updateProfile(draft.trim() || null, data.session.access_token);
      setDisplayName(profile.display_name);
      setOpen(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save your name.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Button
        size="small"
        variant="text"
        color="inherit"
        startIcon={<Icon name="edit" />}
        onClick={handleOpen}
        sx={{ display: { xs: "none", sm: "inline-flex" }, color: "text.secondary", textTransform: "none", fontWeight: 400 }}
      >
        {displayName ?? email}
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Display name</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            Shown instead of your email address on things like a course certificate. Leave
            it blank to fall back to {email}.
          </DialogContentText>
          <TextField
            autoFocus
            fullWidth
            label="Display name"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            slotProps={{ htmlInput: { maxLength: 80 } }}
          />
          {error ? <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert> : null}
        </DialogContent>
        <DialogActions>
          <Button variant="text" onClick={() => setOpen(false)} disabled={saving}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => void handleSave()}
            disabled={saving}
            startIcon={saving ? <CircularProgress size={16} sx={{ color: "inherit" }} /> : undefined}
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
