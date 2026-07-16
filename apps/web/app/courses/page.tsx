import Link from "next/link";
import { redirect } from "next/navigation";
import { CourseDashboard } from "@/components/course-dashboard";
import { createClient } from "@/lib/supabase/server";

export default async function CoursesPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <main className="shell">
      <nav className="nav"><Link className="brand" href="/">SourceLab</Link><span className="muted">{user.email}</span></nav>
      <header className="page-header"><div><span className="eyebrow">Learning library</span><h1>Your courses</h1><p className="muted">Each course has its own source set, route, and mastery record.</p></div><Link className="button-link" href="/courses/new">New course</Link></header>
      <CourseDashboard />
    </main>
  );
}
