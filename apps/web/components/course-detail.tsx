"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@base-ui/react/button";
import { CourseMapResponse, CourseProgressResponse, CourseSummary, getCourse, getCourseMap, getCourseProgress, regenerateCourse } from "@/lib/api";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { CourseProgressSteps } from "@/components/course-progress";
import { createClient } from "@/lib/supabase/client";

const pollIntervalMs = 4000;

export function CourseDetail({ courseId }: { courseId: string }) {
  const [course, setCourse] = useState<CourseSummary>();
  const [progress, setProgress] = useState<CourseProgressResponse>();
  const [map, setMap] = useState<CourseMapResponse>();
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string>();
  const [regenerating, setRegenerating] = useState(false);
  const loadRef = useRef<() => Promise<void>>(async () => {});

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) return;
      try {
        const token = data.session.access_token;
        const [courseSummary, courseProgress] = await Promise.all([getCourse(courseId, token), getCourseProgress(courseId, token)]);
        if (cancelled) return;
        setCourse(courseSummary);
        setProgress(courseProgress);

        const planExists = courseProgress.stage === "ready" || courseProgress.stage === "building_lessons";
        let courseMap: CourseMapResponse | undefined;
        if (planExists) courseMap = await getCourseMap(courseId, token);
        if (cancelled) return;
        setMap(courseMap);
        setState("ready");
      } catch (caught) {
        if (!cancelled) {
          setErrorMessage(caught instanceof Error ? caught.message : "Unknown error.");
          setState("error");
        }
      }
    }

    loadRef.current = load;
    void load();
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  useEffect(() => {
    if (!progress || progress.stage === "ready" || progress.stage === "failed") return;
    const timer = setTimeout(() => void loadRef.current(), pollIntervalMs);
    return () => clearTimeout(timer);
  }, [progress]);

  async function handleRegenerate() {
    setRegenerating(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      await regenerateCourse(courseId, data.session.access_token);
      setMap(undefined);
      setState("loading");
      await loadRef.current();
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Unable to regenerate the course.");
      setState("error");
    } finally {
      setRegenerating(false);
    }
  }

  if (state === "loading") return <p className="muted">Loading course…</p>;
  if (state === "error") return <p className="error">{errorMessage ?? "We could not load this course."}</p>;
  if (!course || !progress) return null;

  return (
    <div>
      <Breadcrumbs items={[{ label: "My courses", href: "/courses" }, { label: course.title }]} />
      <header className="page-header">
        <div>
          <span className="eyebrow">{course.status}</span>
          <h1>{course.title}</h1>
          <p className="muted">{course.goal}</p>
        </div>
        <Button className="button button-secondary" onClick={handleRegenerate} disabled={regenerating} focusableWhenDisabled>
          {regenerating ? "Starting…" : "Regenerate"}
        </Button>
      </header>

      {!map ? (
        <CourseProgressSteps progress={progress} />
      ) : (
        <>
          {progress.stage === "building_lessons" ? <CourseProgressSteps progress={progress} /> : null}
          {map.concepts.length === 0 ? (
            <p className="muted">This course has no concepts yet.</p>
          ) : (
            <div className="course-list">
              {map.concepts.map((concept) => (
                <article className="course-row" key={concept.slug}>
                  <div>
                    <h2>{concept.title}</h2>
                    <p className="muted">{concept.summary_markdown}</p>
                  </div>
                  <span className="course-status">{concept.kind}</span>
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
