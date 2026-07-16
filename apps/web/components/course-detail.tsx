"use client";

import { useEffect, useRef, useState } from "react";
import { Accordion } from "@base-ui/react/accordion";
import { Button } from "@base-ui/react/button";
import { CourseMapResponse, CourseProgressResponse, CourseSummary, getCourse, getCourseMap, getCourseProgress, regenerateCourse } from "@/lib/api";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { CourseCategoryBadge } from "@/components/course-category-badge";
import { CourseProgressSteps } from "@/components/course-progress";
import { Icon } from "@/components/icon";
import { createClient } from "@/lib/supabase/client";

const pollIntervalMs = 2500;

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
        const [courseSummary, courseProgress, courseMap] = await Promise.all([
          getCourse(courseId, token),
          getCourseProgress(courseId, token),
          getCourseMap(courseId, token)
        ]);
        if (cancelled) return;
        setCourse(courseSummary);
        setProgress(courseProgress);
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
  if (!course || !progress || !map) return null;

  return (
    <div>
      <Breadcrumbs items={[{ label: "My courses", href: "/courses" }, { label: course.title }]} />
      <header className="page-header">
        <div className="course-row-main">
          <CourseCategoryBadge title={course.title} goal={course.goal} />
          <div>
            <span className="eyebrow">{course.status}</span>
            <h1>{course.title}</h1>
            <p className="muted">{course.goal}</p>
          </div>
        </div>
        <Button className="button button-secondary" onClick={handleRegenerate} disabled={regenerating} focusableWhenDisabled>
          {regenerating ? "Starting…" : "Regenerate"}
        </Button>
      </header>

      {progress.stage !== "ready" ? <CourseProgressSteps progress={progress} /> : null}

      {map.modules.length === 0 ? (
        progress.stage === "ready" ? <p className="muted">This course has no modules yet.</p> : null
      ) : (
        <Accordion.Root className="module-list">
          {map.modules.map((module) => (
            <Accordion.Item className="module-block" value={module.position} key={module.position}>
              <Accordion.Header>
                <Accordion.Trigger className="module-trigger">
                  <span className="module-title">
                    {module.position}. {module.title}
                  </span>
                  <span className="module-trigger-meta">
                    <span className="muted">
                      {module.concepts.length === 0
                        ? "Generating…"
                        : `${module.concepts.length} concept${module.concepts.length === 1 ? "" : "s"}`}
                    </span>
                    <Icon name="expand_more" className="module-trigger-chevron" />
                  </span>
                </Accordion.Trigger>
              </Accordion.Header>
              <Accordion.Panel className="module-panel">
                {module.concepts.length === 0 ? (
                  <p className="muted">Generating concepts…</p>
                ) : (
                  <div className="course-list">
                    {module.concepts.map((concept) => (
                      <article className="course-row" key={concept.slug}>
                        <div>
                          <h3>{concept.title}</h3>
                          <p className="muted">{concept.summary_markdown}</p>
                        </div>
                        <span className="course-status">{concept.kind}</span>
                      </article>
                    ))}
                  </div>
                )}
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion.Root>
      )}
    </div>
  );
}
