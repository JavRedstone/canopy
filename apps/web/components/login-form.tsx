"use client";

import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import Alert from "@mui/material/Alert";
import Stack from "@mui/material/Stack";
import { FormEvent, useState } from "react";
import { createClient } from "@/lib/supabase/client";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(undefined);
    setMessage(undefined);

    const supabase = createClient();
    const { error: authError } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` }
    });

    setLoading(false);
    if (authError) {
      setError(authError.message);
      return;
    }
    setMessage("Check your inbox for the secure sign-in link.");
  }

  return (
    <Stack component="form" sx={{ gap: 2.5, maxWidth: 480, mt: 3 }} onSubmit={handleSubmit}>
      <TextField
        label="Email address"
        id="email"
        name="email"
        type="email"
        autoComplete="email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        required
        fullWidth
      />
      {message ? <Alert severity="success" role="status">{message}</Alert> : null}
      {error ? <Alert severity="error" role="alert">{error}</Alert> : null}
      <Button variant="contained" type="submit" disabled={loading}>
        {loading ? "Sending link…" : "Email me a sign-in link"}
      </Button>
    </Stack>
  );
}
