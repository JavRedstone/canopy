export interface CourseSummary {
  id: string;
  title: string;
  goal: string;
  status: "draft" | "ready" | "archived";
  active_version: number;
  updated_at: string;
}

export interface CourseMapConcept {
  slug: string;
  title: string;
  kind: "conceptual" | "coding";
  summary_markdown: string;
}

export interface CourseMapModule {
  title: string;
  position: number;
  concepts: CourseMapConcept[];
}

export interface CourseMapResponse {
  course_id: string;
  version: number;
  modules: CourseMapModule[];
}

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getCourses(accessToken: string): Promise<CourseSummary[]> {
  const response = await fetch(`${apiUrl}/api/v1/courses`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load courses (HTTP ${response.status}).`);
  return response.json();
}

export async function getCourse(courseId: string, accessToken: string): Promise<CourseSummary> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load the course (HTTP ${response.status}).`);
  return response.json();
}

export class CoursePlanningNotStartedError extends Error {}

export async function getCourseMap(courseId: string, accessToken: string): Promise<CourseMapResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/map`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (response.status === 409) throw new CoursePlanningNotStartedError("Course planning has not started.");
  if (!response.ok) throw new Error(`Unable to load the course map (HTTP ${response.status}).`);
  return response.json();
}

export type CourseProgressStage = "ingesting_sources" | "planning" | "building_lessons" | "ready" | "failed";

export interface CourseProgressResponse {
  course_id: string;
  stage: CourseProgressStage;
  sources_ready: number;
  sources_total: number;
  lessons_built: number;
  lessons_total: number;
  current_lesson_title: string | null;
}

export async function getCourseProgress(courseId: string, accessToken: string): Promise<CourseProgressResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/progress`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load course progress (HTTP ${response.status}).`);
  return response.json();
}

export async function regenerateCourse(courseId: string, accessToken: string): Promise<CourseSummary> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/regenerate`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  if (!response.ok) throw new Error(`Unable to regenerate the course (HTTP ${response.status}).`);
  return response.json();
}

export interface LessonWorkspaceFile {
  path: string;
  content: string;
}

export type LessonBuildStatus = "pending" | "building" | "built" | "failed";

export interface LessonPreview {
  status: LessonBuildStatus;
  title: string;
  explanation_markdown: string;
  starter_files: LessonWorkspaceFile[];
  hints: string[];
  public_test_files: LessonWorkspaceFile[];
}

export interface ConceptDetailResponse {
  slug: string;
  title: string;
  kind: "conceptual" | "coding";
  summary_markdown: string;
  citations: string[];
  generation_status: LessonBuildStatus | null;
  lesson: LessonPreview | null;
}

export interface LessonRunResult {
  passed: boolean;
  output: string;
  timed_out: boolean;
}

export async function getConceptDetail(courseId: string, slug: string, accessToken: string): Promise<ConceptDetailResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/concepts/${slug}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load this concept (HTTP ${response.status}).`);
  return response.json();
}

export async function runLesson(courseId: string, slug: string, files: LessonWorkspaceFile[], accessToken: string): Promise<LessonRunResult> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/concepts/${slug}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ files })
  });
  if (!response.ok) throw new Error(`Unable to run exercise tests (HTTP ${response.status}).`);
  return response.json();
}

export interface ScriptRunResult {
  output: string;
  exit_code: number;
  timed_out: boolean;
}

export async function runLessonScript(
  courseId: string,
  slug: string,
  files: LessonWorkspaceFile[],
  script: LessonWorkspaceFile,
  accessToken: string
): Promise<ScriptRunResult> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/concepts/${slug}/run-script`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ files, script })
  });
  if (!response.ok) throw new Error(`Unable to run your script (HTTP ${response.status}).`);
  return response.json();
}

export async function regenerateLesson(courseId: string, slug: string, accessToken: string): Promise<void> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/concepts/${slug}/regenerate`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  if (!response.ok) throw new Error(`Unable to regenerate this lesson (HTTP ${response.status}).`);
}
