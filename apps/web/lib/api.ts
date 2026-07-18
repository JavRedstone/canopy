export interface CourseSummary {
  id: string;
  title: string;
  goal: string;
  status: "draft" | "ready" | "archived";
  active_version: number;
  updated_at: string;
  quiz_max_attempts: number;
  lessons_completed: number;
  lessons_total: number;
}

export interface CourseMapConcept {
  slug: string;
  title: string;
  kind: "conceptual" | "coding" | "assessment";
  summary_markdown: string;
  completed: boolean;
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

export interface CoursePointsResponse {
  course_id: string;
  points_earned: number;
  points_total: number;
  points_per_lesson: number;
}

export async function getCoursePoints(courseId: string, accessToken: string): Promise<CoursePointsResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/points`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load course points (HTTP ${response.status}).`);
  return response.json();
}

export interface ConceptMastery {
  slug: string;
  title: string;
  kind: "conceptual" | "coding" | "assessment";
  // null until the track has at least one observation (show as "—", not 0%).
  p_understand: number | null;
  p_apply: number | null;
  understand_opportunities: number;
  apply_opportunities: number;
  mastered: boolean;
}

export interface CourseMasteryResponse {
  course_id: string;
  threshold: number;
  concepts: ConceptMastery[];
}

export async function getCourseMastery(courseId: string, accessToken: string): Promise<CourseMasteryResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/mastery`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load course mastery (HTTP ${response.status}).`);
  return response.json();
}

export interface PrerequisiteConcept {
  slug: string;
  title: string;
  kind: "conceptual" | "coding" | "assessment";
  p_understand: number | null;
  p_apply: number | null;
  mastered: boolean;
  // Practiced but shaky -- reviewing it should help the concept that builds on it.
  needs_review: boolean;
}

export interface PrerequisiteReviewResponse {
  course_id: string;
  slug: string;
  threshold: number;
  review_threshold: number;
  prerequisites: PrerequisiteConcept[];
  review_recommended: boolean;
}

export async function getConceptPrerequisites(courseId: string, slug: string, accessToken: string): Promise<PrerequisiteReviewResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/concepts/${slug}/prerequisites`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load prerequisites (HTTP ${response.status}).`);
  return response.json();
}

export interface UpdateCourseRequest {
  title?: string;
  quiz_max_attempts?: number;
}

export async function updateCourse(courseId: string, request: UpdateCourseRequest, accessToken: string): Promise<CourseSummary> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify(request)
  });
  if (!response.ok) throw new Error(`Unable to update the course (HTTP ${response.status}).`);
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

export async function deleteCourse(courseId: string, accessToken: string): Promise<void> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  if (!response.ok) throw new Error(`Unable to delete the course (HTTP ${response.status}).`);
}

export interface LessonWorkspaceFile {
  path: string;
  content: string;
}

export type LessonBuildStatus = "pending" | "building" | "built" | "failed";

export interface WorkedExamplePreview {
  title: string;
  body_markdown: string;
}

export interface QuizOptionPreview {
  text: string;
}

export type QuizKind = "mcq" | "multi_select" | "fill" | "short_answer";

export interface QuizItemPreview {
  id: string;
  kind: QuizKind;
  prompt_markdown: string;
  options: QuizOptionPreview[];
  attempts_used: number;
  correct: boolean | null;
  previous_answer: QuizAnswerRequest | null;
  previous_grade: QuizGradeResponse | null;
}

export interface QuizAnswerRequest {
  selected_option_index?: number;
  selected_option_indices?: number[];
  answer_text?: string;
}

export interface QuizOptionGrade {
  text: string;
  explanation_markdown: string;
  correct: boolean;
}

export interface QuizGradeResponse {
  item_id: string;
  correct: boolean;
  explanation_markdown: string;
  options: QuizOptionGrade[];
  correct_answers: string[];
  feedback_markdown: string | null;
  attempts_used: number;
  attempts_remaining: number;
}

export interface LessonPreview {
  status: LessonBuildStatus;
  title: string;
  explanation_markdown: string;
  starter_files: LessonWorkspaceFile[];
  hints: string[];
  public_test_files: LessonWorkspaceFile[];
  solution_files: LessonWorkspaceFile[];
  worked_examples: WorkedExamplePreview[];
  quiz_items: QuizItemPreview[];
  quiz_max_attempts: number;
}

export interface ConceptDetailResponse {
  slug: string;
  title: string;
  kind: "conceptual" | "coding" | "assessment";
  summary_markdown: string;
  citations: string[];
  generation_status: LessonBuildStatus | null;
  lesson: LessonPreview | null;
}

export async function resumeCourseLessons(courseId: string, accessToken: string): Promise<void> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/resume-lessons`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  if (!response.ok) throw new Error(`Unable to resume remaining lessons (HTTP ${response.status}).`);
}

export interface LessonHelperResponse {
  answer_markdown: string;
  replacement_markdown: string | null;
}

export async function askLessonHelper(
  courseId: string,
  slug: string,
  question: string,
  selectedText: string | undefined,
  accessToken: string,
  requestRevision = false
): Promise<LessonHelperResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/concepts/${slug}/helper`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ question, selected_text: selectedText, request_revision: requestRevision })
  });
  if (!response.ok) throw new Error(`The learning helper is unavailable (HTTP ${response.status}).`);
  return response.json();
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

// Submit runs the full suite (visible + hidden checks) and records an applied-skill
// mastery observation server-side. Run (above) is visible-only with no mastery effect.
export async function submitLesson(courseId: string, slug: string, files: LessonWorkspaceFile[], accessToken: string): Promise<LessonRunResult> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/concepts/${slug}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ files })
  });
  if (!response.ok) throw new Error(`Unable to submit your solution (HTTP ${response.status}).`);
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

export async function answerQuizItem(
  courseId: string,
  slug: string,
  itemId: string,
  answer: QuizAnswerRequest,
  accessToken: string
): Promise<QuizGradeResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/concepts/${slug}/quiz-items/${itemId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify(answer)
  });
  if (!response.ok) throw new Error(`Unable to grade your answer (HTTP ${response.status}).`);
  return response.json();
}

export async function regenerateLesson(courseId: string, slug: string, accessToken: string): Promise<void> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/concepts/${slug}/regenerate`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  if (!response.ok) throw new Error(`Unable to regenerate this lesson (HTTP ${response.status}).`);
}
