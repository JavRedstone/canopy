import { redirect } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { DesktopOnly } from "@/components/desktop-only";
import { createClient } from "@/lib/supabase/server";

export default async function CoursesLayout({ children }: LayoutProps<"/courses">) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  // Outside AppShell, not inside it: a small screen should get the notice on its own
  // rather than the app's header and nav wrapped around a dead end.
  return (
    <DesktopOnly>
      <AppShell email={user.email ?? "Signed in"}>
        {children}
      </AppShell>
    </DesktopOnly>
  );
}
