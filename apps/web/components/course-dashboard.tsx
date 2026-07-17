"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CourseSummary, getCourses } from "@/lib/api";
import { CourseCategoryBadge } from "@/components/course-category-badge";
import { createClient } from "@/lib/supabase/client";

export function CourseDashboard() {
  const [courses, setCourses] = useState<CourseSummary[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string>();

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function load() {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) return;
      try {
        const nextCourses = await getCourses(data.session.access_token);
        if (cancelled) return;
        setCourses(nextCourses);
        setState("ready");
        if (nextCourses.some((course) => course.status === "draft")) {
          timer = window.setTimeout(() => void load(), 8000);
        }
      } catch (caught) {
        if (!cancelled) {
          setErrorMessage(caught instanceof Error ? caught.message : "Unknown error.");
          setState("error");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  if (state === "loading") return <p className="muted">Loading your courses…</p>;
  if (state === "error") return <p className="error">{errorMessage ?? "We could not load courses."}</p>;
  if (courses.length === 0) {
    return <div className="card"><h2>Your first course starts with a source.</h2><p>Upload a document, choose a goal, and we will create a stable course map.</p><Link className="button" href="/courses/new">Create a course</Link></div>;
  }
  return (
    <div className="course-list">
      {courses.map((course) => (
        <Link className="course-row" href={`/courses/${course.id}`} key={course.id}>
          <div className="course-row-main">
            <CourseCategoryBadge title={course.title} goal={course.goal} />
            <div><h2>{course.title}</h2><p className="muted">{course.goal}</p></div>
          </div>
          {course.status === "draft" ? (
            <span className="course-status course-status-building"><span className="spinner" aria-hidden="true" /> Building…</span>
          ) : (
            <span className="course-status">{course.status}</span>
          )}
        </Link>
      ))}
    </div>
  );
}
