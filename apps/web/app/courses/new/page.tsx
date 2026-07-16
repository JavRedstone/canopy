import Link from "next/link";
import { redirect } from "next/navigation";
import { NewCourseForm } from "@/components/new-course-form";
import { createClient } from "@/lib/supabase/server";

export default async function NewCoursePage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");
  return (
    <main className="shell">
      <nav className="nav"><Link className="brand" href="/courses">SourceLab</Link></nav>
      <section className="hero" style={{ maxWidth: 620 }}><span className="eyebrow">New canonical course</span><h1>Start from a source you trust.</h1><p>Choose a document and define the learning goal that should shape its course map.</p><NewCourseForm /></section>
    </main>
  );
}
