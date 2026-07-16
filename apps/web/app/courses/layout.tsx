import Link from "next/link";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Icon } from "@/components/icon";
import { SidebarNav } from "@/components/sidebar-nav";
import { SignOutButton } from "@/components/sign-out-button";
import { createClient } from "@/lib/supabase/server";

export default async function CoursesLayout({ children }: LayoutProps<"/courses">) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <AppShell
      sidebar={
        <>
          <Link className="brand" href="/">Canopy</Link>
          <Link className="button sidebar-new-button" href="/courses/new">
            <Icon name="add" /> New course
          </Link>
          <SidebarNav />
          <div className="sidebar-user">
            <span className="muted">{user.email}</span>
            <SignOutButton />
          </div>
        </>
      }
    >
      {children}
    </AppShell>
  );
}
