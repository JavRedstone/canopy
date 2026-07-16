"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CourseSummary, getCourses } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

export function CourseDashboard() {
  const [courses, setCourses] = useState<CourseSummary[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    async function load() {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) return;
      try {
        setCourses(await getCourses(data.session.access_token));
        setState("ready");
      } catch {
        setState("error");
      }
    }
    void load();
  }, []);

  if (state === "loading") return <p className="muted">Loading your courses…</p>;
  if (state === "error") return <p className="error">We could not load courses. Confirm that the API is running.</p>;
  if (courses.length === 0) {
    return <div className="card"><h2>Your first course starts with a source.</h2><p>Upload a document, choose a goal, and we will create a stable course map.</p><Link className="button" href="/courses/new">Create a course</Link></div>;
  }
  return (
    <div className="course-list">
      {courses.map((course) => (
        <article className="course-row" key={course.id}>
          <div><h2>{course.title}</h2><p className="muted">{course.goal}</p></div>
          <span className="course-status">{course.status}</span>
        </article>
      ))}
    </div>
  );
}
