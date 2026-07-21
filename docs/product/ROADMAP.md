# Roadmap / To-do

Candidate features and improvements. Checked items have shipped and are verified in the
running code, not just planned; see [`USE_CASES.md`](./USE_CASES.md) for how "shipped"
is verified. Unchecked items are still just candidates.

## Content & pedagogy

- [x] **Fill-in-the-blank question type**: a fourth quiz kind (`fill`) alongside
  mcq/multi-select/short-answer, generated, graded, and mastery-tracked end to end
  (`services/api/app/quiz.py`, `apps/web/components/quiz.tsx`).
- [x] **Multiple coding-lab environments**: courses support `python-basic`, `python-ml`
  (GPU-capable PyTorch/scikit-learn), and `cpp-basic`. The shared registry also provides
  `c-basic` (AddressSanitizer-hardened), `javascript-basic`, and `go-basic` to the
  standalone playground; extending course generation to those three remains future work
  (`services/sandbox_runner/sandbox_runner/runner.py`).
- [ ] **Multiple content languages**: generate and serve courses in languages other than
  English. (Not to be confused with the coding-lab *environments* above, which are
  shipped.)
- [ ] **Adaptive course progression**: sequence lessons based on demonstrated mastery
  rather than a fixed order; add spaced re-retrieval of already-mastered concepts instead
  of marking them done forever. Highest-confidence pedagogy fix per
  [`PEDAGOGY_EVALUATION.md`](./PEDAGOGY_EVALUATION.md#5-bottom-line); reuses the quiz
  engine already built.
- [x] **Non-repeating question bank for practice**: prefer unseen questions, then
  least-recently-seen questions, and top up a concept's pool in the background
  (`services/api/app/practice.py`, `services/worker/worker/practice_pool_build.py`).
- [ ] **Rotating questions in graded lesson attempts**: graded lesson quizzes remain
  fixed, so retries still serve the same questions.
- [ ] **Adaptive remediation trigger**: replace the flat "N failed attempts" constant
  with something sensitive to learner level, per the assistance-dilemma research in
  `PEDAGOGY_EVALUATION.md` §4.3.
- [ ] **Increase robustness of general content (multiple agents?)**: use multiple
  generation/validation agents to raise content quality and catch errors, beyond the
  sandbox-verification repair loop that already exists for labs.

## Learner experience

- [x] **Certificate of completion**: issued once every lesson in a course is done;
  auto-pops up on visiting a finished course, downloadable as a PDF
  (`services/api/app/certificate_pdf.py`, `apps/web/components/certificate-dialog.tsx`).
- [x] **Course export**: the full course exports as a real PDF coursebook
  (`export_coursebook`/`render_textbook_pdf`).
- [x] **Free course sharing**: an owner can share a course by id; anyone who imports it
  gets their own independent copy, no regeneration cost
  (`import_shared_course`, `supabase/migrations/20260719000000_course_sharing_and_import.sql`).
- [x] **Practice mode**: low-stakes concept- and course-level drills with configurable
  order/filter/length, immediate feedback, and positive-only mastery credit capped below
  the mastery threshold (`apps/web/components/practice-drill.tsx`).
- [ ] **Cohort/manager view**: a real org/team layer so a course can be assigned to a
  group with a shared progress dashboard, not just Google-Docs-style link sharing. The
  single biggest structural gap today (`courses.owner_id` is the only authorization axis
  in the schema); see [`USE_CASES.md`](./USE_CASES.md#whats-still-missing).
- [ ] **Repository/codebase ingestion**: point a course at a GitHub repo instead of
  uploading files by hand.

## Rendering & UI

- [x] **Proper markdown / LaTeX support**: KaTeX-rendered math and full Markdown
  (including fenced code) in lesson content and quiz options
  (`apps/web/components/markdown-text.tsx`).
- [ ] **General UI improvements**: broad polish pass across the web app.
- [ ] **Diagrams**: support diagrams in lesson content. The feature is shelved; the
  evaluated Mermaid design and its rendering/security findings are preserved in
  [`archive/DIAGRAM_GENERATION.md`](../archive/DIAGRAM_GENERATION.md).
