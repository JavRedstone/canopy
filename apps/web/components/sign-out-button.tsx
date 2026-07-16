"use client";

import { Button } from "@base-ui/react/button";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export function SignOutButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleSignOut() {
    setLoading(true);
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <Button className="button button-secondary" onClick={handleSignOut} disabled={loading} focusableWhenDisabled>
      {loading ? "Signing out…" : "Sign out"}
    </Button>
  );
}
