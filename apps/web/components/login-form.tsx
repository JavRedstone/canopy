"use client";

import { Button } from "@base-ui/react/button";
import { Input } from "@base-ui/react/input";
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
    <form className="form" onSubmit={handleSubmit}>
      <label className="field" htmlFor="email">
        Email address
        <Input
          className="input"
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </label>
      {message ? <p className="notice" role="status">{message}</p> : null}
      {error ? <p className="error" role="alert">{error}</p> : null}
      <Button className="button" type="submit" disabled={loading} focusableWhenDisabled>
        {loading ? "Sending link…" : "Email me a sign-in link"}
      </Button>
    </form>
  );
}
