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
