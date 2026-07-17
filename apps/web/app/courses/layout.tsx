import { redirect } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { createClient } from "@/lib/supabase/server";

export default async function CoursesLayout({ children }: LayoutProps<"/courses">) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <AppShell email={user.email ?? "Signed in"}>
      {children}
    </AppShell>
  );
}
