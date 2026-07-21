"use client";

import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import Alert from "@mui/material/Alert";
import Stack from "@mui/material/Stack";
import { FormEvent, useState } from "react";
import { createClient } from "@/lib/supabase/client";

/** Chrome's native "Please fill out this field" bubble can't be styled, so the form is
 *  noValidate and the same checks are surfaced through the TextField's own error state. */
function validateEmail(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "Enter your email address.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) return "Enter a valid email address.";
  return undefined;
}

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string>();
  const [error, setError] = useState<string>();
  const [emailError, setEmailError] = useState<string>();
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationError = validateEmail(email);
    if (validationError) {
      setEmailError(validationError);
      return;
    }

    setEmailError(undefined);
    setLoading(true);
    setError(undefined);
    setMessage(undefined);

    const supabase = createClient();
    const { error: authError } = await supabase.auth.signInWithOtp({
      email: email.trim(),
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
    <Stack component="form" noValidate sx={{ gap: 2.5, mt: 3 }} onSubmit={handleSubmit}>
      <TextField
        label="Email address"
        id="email"
        name="email"
        type="email"
        autoComplete="email"
        value={email}
        // Once a message is showing, re-check on every keystroke so it clears as they fix it.
        onChange={(event) => {
          setEmail(event.target.value);
          if (emailError) setEmailError(validateEmail(event.target.value));
        }}
        error={Boolean(emailError)}
        helperText={emailError}
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
