export type CourseLanguage = "python" | "python-ml" | "cpp";

export interface CourseSummary {
  id: string;
  title: string;
  goal: string;
  status: "draft" | "ready" | "archived";
  active_version: number;
  updated_at: string;
  quiz_max_attempts: number;
  lesson_min: number;
  lesson_max: number;
  lessons_completed: number;
  lessons_total: number;
  language: CourseLanguage;
  // True once the owner turns on link sharing: anyone with the course id can import a copy.
  is_shared: boolean;
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

export async function exportCoursebook(courseId: string, accessToken: string): Promise<Blob> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/export/coursebook`, {
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  if (!response.ok) throw new Error(`Unable to export the coursebook (HTTP ${response.status}).`);
  return response.blob();
}

export interface CertificateResponse {
  course_id: string;
  course_title: string;
  learner_name: string;
  issued_at: string;
  certificate_id: string;
  verify_url: string;
  skills: string[];
  estimated_hours: number;
  accent_color: string;
  accent_tint: string;
}

export class CourseNotCompletedError extends Error {}

export async function getCertificate(courseId: string, accessToken: string): Promise<CertificateResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/certificate`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (response.status === 409) throw new CourseNotCompletedError("This course is not fully completed yet.");
  if (!response.ok) throw new Error(`Unable to load the certificate (HTTP ${response.status}).`);
  return response.json();
}

export async function exportCertificate(courseId: string, accessToken: string): Promise<Blob> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/export/certificate`, {
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  if (response.status === 409) throw new CourseNotCompletedError("This course is not fully completed yet.");
  if (!response.ok) throw new Error(`Unable to export the certificate (HTTP ${response.status}).`);
  return response.blob();
}

// No auth token: the durable verification link is meant to work for anyone it's shared
// with, the same way an unauthenticated recipient can open a shared course-import link.
export async function getPublicCertificate(certificateId: string): Promise<CertificateResponse> {
  const response = await fetch(`${apiUrl}/api/v1/certificates/${certificateId}`, { cache: "no-store" });
  if (response.status === 404) throw new Error("Certificate not found.");
  if (!response.ok) throw new Error(`Unable to load the certificate (HTTP ${response.status}).`);
  return response.json();
}

export async function exportPublicCertificate(certificateId: string): Promise<Blob> {
  const response = await fetch(`${apiUrl}/api/v1/certificates/${certificateId}/export`);
  if (!response.ok) throw new Error(`Unable to export the certificate (HTTP ${response.status}).`);
  return response.blob();
}

export interface ProfileResponse {
  email: string;
  display_name: string | null;
}

export async function getProfile(accessToken: string): Promise<ProfileResponse> {
  const response = await fetch(`${apiUrl}/api/v1/profile`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load your profile (HTTP ${response.status}).`);
  return response.json();
}

export async function updateProfile(displayName: string | null, accessToken: string): Promise<ProfileResponse> {
  const response = await fetch(`${apiUrl}/api/v1/profile`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ display_name: displayName })
  });
  if (!response.ok) throw new Error(`Unable to update your profile (HTTP ${response.status}).`);
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

// Returned inline on a graded answer/submission when the learner is struggling on a concept
// that builds on shaky prerequisites -- the shape behind the "review this first" nudge.
export interface PrerequisiteRecommendation {
  concept_slug: string;
  concept_title: string;
  reason_markdown: string;
  prerequisites: PrerequisiteConcept[];
}

export async function getConceptPrerequisites(courseId: string, slug: string, accessToken: string): Promise<PrerequisiteReviewResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/concepts/${slug}/prerequisites`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load prerequisites (HTTP ${response.status}).`);
  return response.json();
}

// One open prerequisite-review recommendation on the course panel: the concept the learner is
// stuck on and the shaky prerequisites (transitive) it builds on, weakest first.
export interface RecommendationSummary {
  id: string;
  concept_slug: string;
  concept_title: string;
  prerequisites: PrerequisiteConcept[];
  created_at: string;
}

export interface RecommendationsResponse {
  course_id: string;
  recommendations: RecommendationSummary[];
}

export type RecommendationDecision = "accepted" | "deferred" | "declined";

export async function getCourseRecommendations(courseId: string, accessToken: string): Promise<RecommendationsResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/recommendations`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load recommendations (HTTP ${response.status}).`);
  return response.json();
}

export async function decideRecommendation(courseId: string, eventId: string, decision: RecommendationDecision, accessToken: string): Promise<void> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/recommendations/${eventId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ decision })
  });
  if (!response.ok) throw new Error(`Unable to update the recommendation (HTTP ${response.status}).`);
}

export interface UpdateCourseRequest {
  title?: string;
  quiz_max_attempts?: number;
  lesson_min?: number;
  lesson_max?: number;
  is_shared?: boolean;
}

export class SharedCourseNotFoundError extends Error {}

// Import a copy of a shared course's content (not progress) by its id. The id is the share
// token: unshared or unknown ids both come back as "not found", by design.
export async function importCourse(courseId: string, accessToken: string): Promise<CourseSummary> {
  const response = await fetch(`${apiUrl}/api/v1/courses/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ course_id: courseId })
  });
  if (response.status === 404) throw new SharedCourseNotFoundError("No shared course was found for that id.");
  if (!response.ok) throw new Error(`Unable to import the course (HTTP ${response.status}).`);
  return response.json();
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
  prerequisite_recommendation?: PrerequisiteRecommendation | null;
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
  requestRevision = false,
  context?: { workspaceFiles?: LessonWorkspaceFile[]; quizItemId?: string }
): Promise<LessonHelperResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/concepts/${slug}/helper`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({
      question,
      selected_text: selectedText,
      request_revision: requestRevision,
      workspace_files: context?.workspaceFiles ?? [],
      quiz_item_id: context?.quizItemId,
    })
  });
  if (!response.ok) throw new Error(`The learning helper is unavailable (HTTP ${response.status}).`);
  return response.json();
}

export interface LessonRunResult {
  passed: boolean;
  output: string;
  timed_out: boolean;
  // Set only by Submit (not Run) when the failed suite leaves apply-mastery stuck.
  prerequisite_recommendation?: PrerequisiteRecommendation | null;
}

export async function getConceptDetail(courseId: string, slug: string, accessToken: string): Promise<ConceptDetailResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/concepts/${slug}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load this concept (HTTP ${response.status}).`);
  return response.json();
}

export interface CitationExcerptResponse {
  id: string;
  filename: string;
  section: string | null;
  page_number: number | null;
  content: string;
}

export async function getCitationExcerpt(courseId: string, citationId: string, accessToken: string): Promise<CitationExcerptResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/citations/${citationId}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load this source excerpt (HTTP ${response.status}).`);
  return response.json();
}

export interface CourseSourceSummary {
  id: string;
  filename: string;
  mime_type: string;
  byte_size: number;
  status: "uploading" | "uploaded" | "ingesting" | "ready" | "failed";
  position: number;
}

export async function getCourseSources(courseId: string, accessToken: string): Promise<CourseSourceSummary[]> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/sources`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to load this course's sources (HTTP ${response.status}).`);
  return response.json();
}

export interface SourceDownloadResponse {
  filename: string;
  mime_type: string;
  download_url: string;
}

export async function getSourceDownloadUrl(courseId: string, sourceId: string, accessToken: string): Promise<SourceDownloadResponse> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/sources/${sourceId}/download`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to prepare this download (HTTP ${response.status}).`);
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

export interface DemoConceptResult {
  concept_slug: string;
  concept_title: string;
  kind: "conceptual" | "coding" | "assessment";
  quiz_items_correct: number;
  quiz_items_incorrect: number;
  quiz_items_skipped: number;
  lab_passed: boolean | null;
  error: string | null;
}

export interface DemoJobStatus {
  job_id: string;
  course_id: string;
  state: "running" | "completed" | "cancelled" | "failed";
  total: number;
  completed: number;
  current_concept_title: string | null;
  results: DemoConceptResult[];
  error: string | null;
}

export interface DemoAutoCompleteOptions {
  target: "mastered" | "mixed";
  correctRate: number;
  // undefined/omitted means every concept in the course.
  conceptSlugs?: string[];
  includeQuizzes: boolean;
  includeLabs: boolean;
}

// Dev-only: the API 404s all of these outside APP_ENVIRONMENT=development. Drives some or
// all of a course to completion as an LLM standing in for the learner, through the real
// grading/sandbox paths -- as a background job, since a full course is real LLM/sandbox
// work that can take minutes. Start it, then poll getDemoAutoCompleteStatus for progress.
export async function startDemoAutoComplete(
  courseId: string,
  options: DemoAutoCompleteOptions,
  accessToken: string
): Promise<DemoJobStatus> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/demo/auto-complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({
      target: options.target,
      correct_rate: options.correctRate,
      concept_slugs: options.conceptSlugs ?? null,
      include_quizzes: options.includeQuizzes,
      include_labs: options.includeLabs
    })
  });
  if (!response.ok) throw new Error(`Unable to start auto-complete (HTTP ${response.status}).`);
  return response.json();
}

export async function getDemoAutoCompleteStatus(courseId: string, jobId: string, accessToken: string): Promise<DemoJobStatus> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/demo/auto-complete/${jobId}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`Unable to check auto-complete status (HTTP ${response.status}).`);
  return response.json();
}

export async function cancelDemoAutoComplete(courseId: string, jobId: string, accessToken: string): Promise<void> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/demo/auto-complete/${jobId}/cancel`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  if (!response.ok) throw new Error(`Unable to cancel auto-complete (HTTP ${response.status}).`);
}

// Dev-only: the undo for startDemoAutoComplete. conceptSlugs omitted clears the whole
// course; otherwise only those lessons' mastery/observations/assignment state is wiped.
export async function clearDemoProgress(courseId: string, conceptSlugs: string[] | undefined, accessToken: string): Promise<void> {
  const response = await fetch(`${apiUrl}/api/v1/courses/${courseId}/demo/clear`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ concept_slugs: conceptSlugs ?? null })
  });
  if (!response.ok) throw new Error(`Unable to clear demo progress (HTTP ${response.status}).`);
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

export type PlaygroundEnvironmentId = "python-basic" | "python-ml" | "javascript-basic" | "go-basic" | "cpp-basic" | "c-basic";

// Each environment's test command auto-discovers test files by its own convention
// (pytest: test_*.py, node --test: *.test.js, go test: *_test.go, doctest: any *.cpp
// file) -- no entry point needed.
export async function runPlayground(environmentId: PlaygroundEnvironmentId, files: LessonWorkspaceFile[], accessToken: string): Promise<LessonRunResult> {
  const response = await fetch(`${apiUrl}/api/v1/playground/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ environment_id: environmentId, files })
  });
  if (!response.ok) throw new Error(`Unable to run this code (HTTP ${response.status}).`);
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
