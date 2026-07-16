"use client";

import { useEffect, useState } from "react";
import { ConceptDetailResponse, CourseSummary, getConceptDetail, getCourse } from "@/lib/api";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { Icon } from "@/components/icon";
import { conceptKindIcon, conceptKindLabel } from "@/lib/concept-kind";
import { createClient } from "@/lib/supabase/client";

export function ConceptDetail({ courseId, slug }: { courseId: string; slug: string }) {
  const [course, setCourse] = useState<CourseSummary>();
  const [concept, setConcept] = useState<ConceptDetailResponse>();
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string>();

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session) return;
      try {
        const token = data.session.access_token;
        const [courseSummary, conceptDetail] = await Promise.all([
          getCourse(courseId, token),
          getConceptDetail(courseId, slug, token)
        ]);
        if (cancelled) return;
        setCourse(courseSummary);
        setConcept(conceptDetail);
        setState("ready");
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
    };
  }, [courseId, slug]);

  if (state === "loading") return <p className="muted">Loading…</p>;
  if (state === "error") return <p className="error">{errorMessage ?? "We could not load this concept."}</p>;
  if (!course || !concept) return null;

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "My courses", href: "/courses" },
          { label: course.title, href: `/courses/${courseId}` },
          { label: concept.title }
        ]}
      />
      <header className="page-header">
        <div className="course-row-main">
          <span className="concept-kind-badge">
            <Icon name={conceptKindIcon(concept.kind)} />
          </span>
          <div>
            <span className="eyebrow">{conceptKindLabel(concept.kind)}</span>
            <h1>{concept.title}</h1>
          </div>
        </div>
      </header>

      <p>{concept.summary_markdown}</p>

      {concept.kind === "coding" ? (
        concept.lesson && concept.lesson.status === "built" ? (
          <div className="lesson-preview">
            {concept.lesson.explanation_markdown ? <p className="muted">{concept.lesson.explanation_markdown}</p> : null}

            {concept.lesson.hints.length > 0 ? (
              <div className="notice">
                <strong>Hints</strong>
                <ul>
                  {concept.lesson.hints.map((hint, index) => (
                    <li key={index}>{hint}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="lesson-files">
              {concept.lesson.starter_files.map((file) => (
                <div className="lesson-file" key={file.path}>
                  <div className="lesson-file-path">{file.path}</div>
                  <pre className="lesson-file-content">{file.content}</pre>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="muted">
            {concept.lesson?.status === "failed"
              ? "This lab could not be built. Try regenerating the course."
              : "This lab is still being built."}
          </p>
        )
      ) : null}
    </div>
  );
}
