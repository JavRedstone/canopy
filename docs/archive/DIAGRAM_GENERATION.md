# Diagram Generation — build doc

How generated diagrams get into lesson content: as **diagram-as-code text**, produced by an
LLM call, validated by a real parser before shipping, rendered as sanitized SVG.

> **Archived — designed, not built.** The feature was shelved after evaluation. This document
> preserves the Mermaid, rendering, security, and AI-image findings so future work can reuse
> them. Current status is tracked in [`ROADMAP.md`](../product/ROADMAP.md).

---

## 1. Why / current state

Lesson content today is prose + worked examples + quiz items + (for coding lessons) a
sandbox-verified lab. There is no visual layer at all. Concepts that are inherently
structural — a request flow, a state machine, a class hierarchy, a data pipeline — get
described in paragraphs.

Nothing in the stack renders a diagram today:

- `apps/web/package.json` has no mermaid, d3, recharts, chart.js, plotly, nivo, visx, or
  `@mui/x-charts`. The only rendering dependencies are `katex` and `motion`.
- `apps/web/components/markdown-text.tsx:276` recognizes a fenced code block with
  `line.trimStart().startsWith("```")` and nothing else — **the info string after the
  fence is parsed nowhere and discarded**. So a ` ```mermaid ` block today renders as a
  plain grey code box with the word "mermaid" invisible.
- `services/api/app/textbook_pdf.py` is a second, independent renderer with its own fence
  handling.

So this is genuinely additive: no existing behavior to preserve, and no silent
half-support to untangle.

---

## 2. Scope

### In: diagram-as-code ✅

The LLM emits **text** in a diagram notation, exactly the way it already emits Python for
coding labs. That text is parsed by a real parser at build time; a diagram that does not
parse never reaches a learner.

### Out: AI image generation ❌ — settled, not deferred

Asking an image model to draw a diagram was evaluated and **rejected**. The evidence,
briefly, because this decision should not be relitigated without new evidence:

| Source | Finding |
|---|---|
| GenEval 2 (Meta FAIR) | Qwen-Image: **99.1%** drawing a specified object, **60.2%** on relative position. Best model overall **84.4%** atom-level vs **32.3%** prompt-level. |
| IGenBench | Whole-image correctness on infographics: best model **0.49**, GPT-Image-1.5 **0.12**. |
| FEPBench | Text-instruction faithfulness collapses to **0.389 / 0.333**; all models poor on *relational* atoms. |
| STRICT | GPT-4o text edit-distance degrades 0.05 → **0.65** from 100 to 5000 characters. |

Object fidelity is effectively solved. **Spatial relations are not — and a diagram is
nothing but relations.**

Three further points make it structural rather than a matter of waiting for better models:

1. **Non-reproducibility.** Neither `gpt-image-2` nor Gemini exposes a seed. This product
   regenerates courses; an artifact that changes on every rebuild and cannot be pinned is
   incompatible with that.
2. **Accessibility makes it redundant.** W3C requires a two-part alternative for complex
   images — short alt *plus* a full textual representation. The prose explanation has to be
   written regardless, so the image is pure additive cost. Worse: auto-captioning a
   generated diagram tends to silently *correct* garbled labels, producing alt text that
   describes a **correct** diagram while sighted learners see a **wrong** one — a
   correctness failure disguised as an accessibility feature.
3. **It would break provider portability.** `services/llm_gateway/llm_gateway/providers.py:17-22`
   defines `ModelProvider` with exactly three methods: `structured`, `respond`, `embed`.
   There are four adapters (OpenAI, Azure, Bedrock Converse, Bedrock-Mantle). Bedrock
   Converse serves Claude Sonnet 4.5 and Bedrock-Mantle serves GPT text models — **neither
   can generate images**. Adding images means the first capability in the system that is
   not provider-portable.

Cost is explicitly *not* the argument: ~$1.60/course at medium quality, ~$6.30 at high, is
noise against existing LLM spend. The case rests on correctness and architecture.

Two external confirmations that diagram-as-code is the right side of this line:
**SciFlow-Bench** ran a code-driven Graphviz baseline against image models on scientific
flow diagrams — it matched the best image model and beat every diffusion model. And
**Springer Nature** bans AI-generated images across 3,000+ journals while *explicitly
exempting* flow charts and text-based display items.

**Narrow exception, deliberately not a pipeline:** non-factual *analogy* illustrations —
no load-bearing labels, no ground truth to contradict — generated once, human-reviewed,
hand-written alt text, stored as immutable assets. A handful of images and a manual
workflow. Not worth touching the gateway protocol for.

⚠️ One relevant pedagogy caveat for whoever revisits this: Sung & Mayer found learners
rated *every* graphic condition as more satisfying, including conditions that measurably
hurt learning. **Decorative imagery would raise engagement metrics while lowering
mastery.** (Two research passes reported this at g=−0.16 and g=−0.33 — direction certain,
magnitude unreconciled.)

---

## 3. Format decision

### Decided: Mermaid ✅

**Chosen 2026-07-20.** The deciding argument is operational, not accuracy: Java appears
nowhere in this stack, while `node:20-slim` is already built and shipped for the
`javascript-basic` sandbox environment — so Mermaid adds two npm packages to existing
infrastructure where PlantUML would add an entire language runtime. Mermaid also has no
remote-service affordance to misuse (§3, PlantUML's `plantuml` PyPI package POSTs over
plain HTTP), and its parse errors support targeted repair where PlantUML's do not.

**What could still overturn this:** if the bake-off (§6, M0) shows this model writing
invalid Mermaid at a high rate *and* the repair loop failing to close the gap, PlantUML's
measured 89–93% first-pass reliability would justify paying the JVM cost. Reliability beats
convenience. D2 remains the second fallback.

**Consequence of the decision:** the `svgdom` rendering risk (§4.5) is now on the critical
path rather than hedged by PlantUML's proven `-tsvg` render. **M0.5 becomes a gating spike,
not an optional one.**

### Why Mermaid over the alternatives

| | Mermaid | D2 | PlantUML | Graphviz |
|---|---|---|---|---|
| Evidence LLMs write it | Plausible (ubiquitous in training data) | **None published** | **Best measured** (89–93%, parser-verified) | Moderate |
| Parse error quality | **Best** — line, column, token, *expected-token set* | Very good — all errors one pass, line+column | **Worst** — no line number | Good |
| Validator cost | 0.68 ms warm (Node + jsdom) | CLI | JVM | `nop -p`, 31 ms |
| Native web rendering | Yes | No | No | Via wasm |
| License | MIT | MPL-2.0 | MIT jars available | EPL-2.0 |

**Mermaid wins on the criterion that actually matters here: repair-loop feedback.** Its
JISON parser emits a machine-readable hash:

```
hash: {"text":"[","token":"SQS","line":1,
       "loc":{"first_line":2,"first_column":4,"last_column":15},
       "expected":["'SQE'","'PE'","'PIPE'", ...]}
```

Line, column, offending token, **and the set of tokens that would have been valid**. That
is close to an ideal input for the regenerate-with-feedback loop this codebase already
runs — and it directly satisfies the contract `validate_practice_pool` states for itself
in `services/worker/worker/lesson_schema.py:404-405`: *"messages are written to be fed
straight back to the model as regeneration feedback."*

Verified behavior: it catches the classic LLM error (unquoted parens in
`A[Load data (CSV)]`) while correctly accepting `<br>`, `&`, commas, emoji, and curly
quotes.

**PlantUML is a live candidate, not eliminated.** It has the best-evidenced LLM reliability
and is MIT-licensable (every release ships parallel `plantuml-mit` / `-asl` / `-bsd` jars).
Its `--check-syntax` returns `Some diagram description contains errors` with **no line
number**, and the `-pipe` path has a confirmed off-by-one — so targeted repair is
effectively off the table.

**But error quality only matters conditional on first-pass rate, and that conditional was
initially missed.** At a measured 91%, blind re-rolling reaches 99.93% in three attempts
(~1.10 expected calls per diagram). A format with excellent errors but a 70% first-pass
rate costs ~1.43 calls to reach 97.3%. PlantUML's *measured* number competes well against
Mermaid's *assumed* one.

PlantUML also removes a risk Mermaid carries: `java -jar plantuml.jar -tsvg` is a
well-trodden server-side render path, whereas Mermaid's browser-free rendering depends on
the unproven `svgdom` route (§4.5) or a heavy Puppeteer fallback. Since §4.5 already argues
for pre-rendering over shipping a client renderer, Mermaid's native-web-rendering advantage
largely evaporates while its rendering *risk* does not.

Where PlantUML still genuinely loses:

- **Correlated failures.** The blind-retry math assumes independence. If the model
  systematically botches one construct, re-rolling hits the same wall every time and
  convergence plateaus. Error-guided repair is what breaks correlation, and PlantUML cannot
  support it. Partial mitigation: systematic failures are often better fixed in the prompt
  manifest (§5) than in a repair loop.
- **Operational weight — larger than it first appears.** Java appears **nowhere** in this
  repo. Meanwhile `services/sandbox_runner/sandbox_image/javascript-basic/Dockerfile` is
  already `FROM node:20-slim` — precisely the base image a Mermaid validator needs. So the
  comparison is not "JVM vs Node runtime"; it is **"add an entirely new language runtime"
  vs "add two npm packages to an image already built and shipped."** The MIT jar and the
  fast native binaries are also **mutually exclusive** (natives are GPL-only), and
  [plantuml#718](https://github.com/plantuml/plantuml/issues/718) questions the relicensing
  mechanism — probably fine, not airtight.
- **A tempting insecure path.** Neither format requires a network service when done
  correctly (Mermaid is an npm library; PlantUML's jar runs locally). But PlantUML has
  convenient remote options — `plantuml-server`, Kroki, and the `plantuml` PyPI package,
  which POSTs source to plantuml.com over **plain HTTP**. Lesson content derives from
  learner-uploaded documents, so that is a genuine data-egress footgun. Mermaid offers no
  equivalent affordance to reach for.

Avoid the `plantuml` PyPI package entirely — it POSTs source to plantuml.com over **plain
HTTP**.

**D2 is the fallback.** It is the only tool reporting *all* errors in a single pass with
line and column. It loses on having no published evidence that LLMs can write it and no
native web rendering. ⚠️ If adopted: `d2 validate` is a trap — it is parse-only and
**passes diagrams that will not render** (`x.shape: nonexistent_shape` exits 0). Use a
full compile (`d2 - - > /dev/null`) as the oracle.

### Gate: run the bake-off before committing

50 representative diagrams through the **actual `lesson_build` model and prompts**,
measuring parser-verified first-pass validity, Mermaid vs D2. No external benchmark
answers the only question that matters: whether *this* model writes valid Mermaid often
enough that the repair loop is cheap. If first-pass validity is low, switch to D2 before
anything is built on it.

This is a small Node script, not a container build.

### Validation runs in Node, not Python

There is no usable pure-Python Mermaid parser. The important correction to the obvious
assumption: **`mermaid.parse()` does not require headless Chromium.** It fails in bare
Node only because DOMPurify needs a `window`, producing
`TypeError: DOMPurify.addHook is not a function` *on valid input* — silent false positives
that would send a repair loop chasing nonexistent bugs. Adding **`jsdom`** (pure JS, no
browser) makes all tested diagram types parse correctly.

Measured: **0.68 ms per parse warm** (200 parses in 136 ms) after ~550 ms cold start — so
keep one Node process alive rather than spawning per diagram.

`@mermaid-js/parser` is **not** a substitute; it returns `Unknown diagram type: flowchart`.

---

## 4. Architecture

### 4.1 Generation pass — its own job

**Decision: diagrams are generated by a separate `diagram_build` job, not inline in
`lesson_build`.** This mirrors `practice_pool_build` exactly, and for the same three
reasons.

`services/worker/worker/practice_pool_build.py:3-6` states the principle:

> Runs as its own `practice_pool_build` generation job… Keeping it off the lesson's
> critical path is the point: the lesson renders as soon as it is built, the pool
> backfills behind it, and a pool failure can never mark a shipped lesson failed.

All three clauses apply verbatim — and there is a fourth reason, specific to diagrams,
that is arguably the strongest:

0. **Prompt dilution.** Asking a single structured call to emit prose, worked examples,
   quiz items *and* diagram source degrades all four. Diagram notation is the most
   syntactically brittle output of the set, and the least like the surrounding prose. This
   codebase already made exactly this call once: `lesson_build.py:3-7` splits content from
   coding artifacts so that "a citation/quiz failure shouldn't force regenerating an
   expensive sandbox-verified exercise," and `CODING_CONTENT_SYSTEM_PROMPT`
   (`lesson_agent.py:42-44`) makes the handoff explicit — *"a matching coding exercise will
   be generated separately from what you write here, so describe the exercise clearly
   enough that it can be built from your description alone."* A diagram pass should take
   the same shape: the content call describes what the diagram must show; the diagram call
   renders it into notation.

1. **Latency.** A conceptual lesson makes exactly **one** LLM call today
   (`services/worker/worker/lesson_build.py:194`). A second serial call on the critical
   path doubles time-to-first-lesson. Nothing is visible to a learner until
   `apply_lesson_bundle` flips `build_status` to `built`, and the API only reads revisions
   with `validation_status='validated'` (`services/api/app/repository.py:1172-1180`).
2. **Docker dependency.** `lesson_build.py:68-74` calls `sandbox.ensure_available()` *only*
   for coding lessons. Validating a diagram needs a Node sandbox environment; doing that
   inline would make **conceptual lessons Docker-dependent**, which they are not today.
   That is a real regression.
3. **Failure isolation — the decisive one.** If diagram validation is folded into
   `validate_lesson_content`, a diagram that will not parse **burns the lesson content's
   retry budget and fails the whole lesson**, including prose and quiz items that were
   fine. `services/worker/worker/runner.py:83-86` already encodes the fix for exactly this
   shape: `practice_pool_build` is excluded from the `retry_lesson_build` branch so a
   failed pool can never spend the lesson's budget.

**A diagram must degrade, never fail the build.** Catch, log, drop the diagram, ship the
lesson.

Enqueued from the sibling position to `_enqueue_practice_pool` (`lesson_build.py:92`).
Excluded from the retry branch in `runner.py:97`.

**Cost of this choice:** one migration. `lesson_revisions` is never modified in place
(`docs/architecture/ARCHITECTURE.md:225`), so a post-hoc diagram needs its own table.

### 4.2 The cheaper alternative, and why it is not recommended

Diagrams could instead live on `LessonContent` in the existing bundle, emitted by the
*existing* content call. That is genuinely cheaper: `bundle_json` is a single opaque
`jsonb` (`supabase/migrations/20260715230000_initial_schema.sql:139`) with no shape
constraints or indexes, `bundle_view` reads with `.get()` defaults throughout, and
`schema_version` is a **read-time dispatch** (`services/api/app/lesson_bundle.py:35-77`)
rather than a stored migration — so an optional `diagrams: list[Diagram] = []` field needs
**zero DDL** and no version bump.

It inherits all three problems above. Take it only if the bake-off shows first-pass
validity high enough that build-time validation can be dropped entirely — in which case
there is no Node dependency and no failure-isolation concern, because there is no
validation step.

⚠️ If taken, one trap: the checkpoint (`pending_content_json`) is all-or-nothing and is
saved *after* content validates (`lesson_build.py:209-212`). Diagram work sequenced
**after** the checkpoint save is silently skipped forever on any worker restart.

### 4.3 Storage

New table, modeled on `supabase/migrations/20260719040000_practice_question_pool.sql`,
keyed on concept + course version. Fields: `mermaid_source`, `alt_text`, `title`,
`notation`, plus the pre-rendered `svg` (§4.5).

Note for anyone restructuring the bundle later: the practice-pool migration reads
`bundle_json` internals **in SQL** (`:131`, `:144`, `:150`), hard-coding the v2 shape.
Additive changes are safe; restructuring `lesson_content` breaks it with no type error and
no test failure.

### 4.4 Validation + repair

Three validation mechanisms exist in the codebase. Only one is the right analogue.

| | Mechanism | Where | Use for diagrams? |
|---|---|---|---|
| A | Schema validation + re-prompt, 3 attempts | `services/worker/worker/llm.py:42-80` | **Free** — length caps, notation enum |
| B | Domain validation + regenerate with feedback, 3 attempts | `lesson_build.py:215-247` | **Yes — this is the pattern** |
| C | Execute-then-repair, agentic tool loop | `lesson_agent.py:541-584` | **No** |

**Mechanism C must not be reused.** It exists to solve a problem diagrams do not have:
path-restricted writes across a multi-file workspace where the model could "fix" a failing
test by editing the test. Hence the allowlist at `lesson_agent.py:568-569` and the rule at
`:582-583` — *"never trust the model's self-report of success — always re-verify with one
more real run."* A diagram is a single string with no adversarial surface.

The loop:

```
generate → parse in Node sandbox → on failure, feed the JISON hash back as `feedback`
         → regenerate (max 3) → on exhaustion, drop the diagram and ship the lesson
```

`validate_practice_pool` (`lesson_schema.py:395-425`) is the model to copy — grounding plus
near-duplicate detection, with messages written for the model rather than for a human.

**Semantic correctness is not addressed and should not be claimed.** A diagram can parse
perfectly and still be pedagogically wrong. Parser validation catches syntax only. Treating
a green parse as evidence of a *correct* diagram would repeat the error
`docs/product/PEDAGOGY_EVALUATION.md` §4.5 identifies about green test suites.

### 4.5 Rendering and security — the highest-risk area

**The current XSS posture is "we never render HTML we did not construct."** There is
exactly **one** `dangerouslySetInnerHTML` in the entire web app
(`apps/web/components/markdown-text.tsx:40`), injecting KaTeX output, and there is **no
DOMPurify, no rehype-sanitize, and no sanitizer dependency anywhere** in the tree. This is
documented as a principle at `docs/architecture/SECURITY.md:66`. The hand-rolled renderer
recognizes a fixed grammar; raw HTML in model output renders as literal text.

Diagram renderers emit **raw SVG**, which can carry `<script>`, `<foreignObject>`, and
event-handler attributes. And diagram source would be LLM-authored **from learner-uploaded
documents** — downstream of input the prompts already treat as an injection vector
(`lesson_agent.py:346-347`).

Three mandatory mitigations:

1. **Pin mermaid ≥ 11.16.0.** CVE-2026-41149 / GHSA-ghcm-xqfw-q4vr is a DOM injection under
   *default* configuration, fixed in 11.15.0.
2. **Set `htmlLabels: false`, and strip `%%{init:` directives before parsing or rendering.**
   Two layers, both required.

   `securityLevel` *is* protected by mermaid's `secure` allowlist and cannot be flipped
   from diagram text — but **`htmlLabels` is not on that list**, so untrusted source can
   turn HTML labels on. Stripping `%%{init:` closes that.

   **The M0.5 spike found this is worse than "an attack vector" — HTML labels are the
   _default_.** Rendering with stock config produced **zero `<text>` elements** for
   flowchart, state, class, and ER; every label came out inside a `<foreignObject>`, i.e.
   arbitrary HTML embedded in the SVG. Setting `htmlLabels: false` (globally *and*
   per-diagram-type — `flowchart`, `class`, `er`, `state` each carry their own) produced
   **9 real `<text>` elements and 0 `foreignObject`** on the same flowchart, with all label
   text intact and no `<script>`/`onload`/`javascript:` anywhere in the output.

   This one setting pays three ways: it removes HTML from the SVG entirely (matching the
   "never render HTML we did not construct" posture), it neutralizes the `htmlLabels`
   vector at the config layer rather than relying solely on input sanitation, and it is
   **required for PDF export** (§4.6) because `foreignObject` does not render in
   SVG-to-PDF pipelines.
3. **Set `deterministicIds: true` with a stable seed.** It defaults to `false`, so IDs are
   random per render and *will* cause Next.js hydration mismatches.

**Prefer pre-rendering to sanitized SVG at build time** over shipping mermaid to the
browser. It sanitizes once server-side under our control, removes the hydration question,
avoids a large client dependency (measured on 11.16.0: UMD **971 KB gzip**; ESM entry
**12 KB gzip**; all 130 code-split chunks summed **533 KB gzip**), and gives the PDF
exporter something usable.

✅ **Browser-free rendering is proven** (M0.5 spike, 2026-07-20, mermaid 11.16.0 / jsdom
29.1.1 / svgdom 0.1.28, Node 22). Neither library works alone:

- **jsdom alone fails** — `CSSStyleSheet is not defined`, then missing text metrics.
- **svgdom alone fails** — it provides an SVG document, not an HTML one, so mermaid's
  container lookup dies on `Cannot read properties of null (reading 'firstChild')`.

**The working configuration is a hybrid:** jsdom supplies the HTML DOM, and svgdom is used
*purely as a font-measurement engine* — `SVGElement.prototype.getBBox` and
`getComputedTextLength` are patched to delegate to an off-screen svgdom text node. svgdom
bundles `OpenSans-Regular.ttf`, so no font installation is required. Measured result:
**5/5 diagram types render** (flowchart, sequence, state, class, ER) at **~28 ms each
warm**. No Chromium, no Puppeteer.

Crude stubs are *not* sufficient: with a naive `width = text.length * 8` estimator,
flowchart and ER both fail with `Could not find a suitable point for the given distance` —
edge routing needs real geometry. Real measurement fixes both.

⚠️ **Remaining fidelity caveat:** label text is word-wrapped across multiple `<tspan>`
elements, and wrap points are driven by the measurement function. `User request` wraps to
two lines here, which suggests OpenSans may over-measure relative to the browser's actual
font. Layout is *correct*, not necessarily *identical to Chromium*. Tune the font mapping
before shipping; this is a polish item, not a blocker.

**Placement in the page.** Follow the worked-example precedent, not the fence precedent:
extend `LESSON_MARKER` at `apps/web/components/concept-detail.tsx:66` from
`(example|quiz)` to `(example|quiz|diagram)` and add a third arm to the `LessonBody` split
loop, mirroring `WorkedExampleCard`. The marker path already skips markers inside code
fences (`:176-180`).

### 4.6 PDF export

`services/api/app/textbook_pdf.py` is a **second, independent renderer** (reportlab), and
it strips lesson markers at `:227`. Math already degrades differently there — KaTeX in the
browser, italic plaintext in the PDF (`:49-59`).

Diagrams need an explicit decision here or they silently vanish from exported coursebooks.
Pre-rendered SVG (§4.5) makes this tractable; otherwise degrade to the alt text.

### 4.7 Model tiering

Register a `diagram_build` task in `GatewayTask`
(`services/llm_gateway/llm_gateway/settings.py:8`) with per-provider model settings and a
`model_for` branch.

The rationale for a *separate* task is the one already written for `practice_pool` at
`settings.py:44-47`: split out so that if evaluation shows weak output, this is the one
dial that can be turned up to Sol **without moving lesson generation with it**.

**Which tier — and why this should be measured, not assumed.** The existing convention is
stated at `settings.py:34-38`: per-concept work runs on Luna; Sol is reserved for one-shot
work (`course_outline`, "one call per course but fixes the whole course's framing") and for
work that only fires on an already-failed artifact (`lesson_repair`, "repair only fires on
labs that already failed their first sandbox run, so it can afford the flagship Sol
reasoning tier where generation cannot").

Diagram generation runs **per concept**, which by that convention puts it on Luna. But
there is a real counter-argument: getting a diagram *structurally* right — correct
topology, correct relations — is closer to reasoning than prose generation is, and a wrong
diagram is more conspicuously wrong than slightly-worse prose.

The economics decide it, and they hinge on one unknown number:

- If Luna's first-pass parser validity is high (~90%), paying Sol on **every** concept to
  avoid repairs on ~10% is bad economics. Keep Luna for generation.
- If Luna's first-pass validity is poor (~50%), the repair loop runs constantly and Sol on
  generation is likely cheaper *and* faster end to end.

**Recommended shape either way: mirror the builder/repair split.** `diagram_build` on Luna,
and — if a repair step is added — `diagram_repair` on Sol, so the expensive tier only fires
on diagrams the parser already rejected. That is precisely the existing
`openai_builder_model` / `openai_repair_model` logic applied to a new flow, and parser
errors (line, column, expected-token set) are exactly the kind of constrained fix a
reasoning tier handles well.

The bake-off (§6, M0) should therefore measure **tier as a second axis** — Mermaid vs D2 ×
Luna vs Sol. Four cells, ~200 generations, cheap. Do not pick a tier by argument when the
measurement costs an hour.

Note that `_tool_repair_loop` hard-codes `model="lesson_repair"` (`lesson_agent.py:558`),
ignoring its `model` parameter — a live convention worth knowing, and possibly a bug.

---

## 5. Prompt design notes

Follow the manifest pattern. `ENVIRONMENT_PACKAGES` (`lesson_agent.py:252-282`) tells the
coding generators exactly what exists, with the rationale at `:246-251`: *"a lab only ever
depends on what exists… If the environment list grows, this is where the model learns its
options."* A diagram manifest is the same idea — enumerate the permitted diagram types,
state what is unavailable, then give a positive stylistic directive.

Two existing prompt constraints must be renegotiated:

- **`MATH_FORMATTING_INSTRUCTION` (`lesson_agent.py:25-30`)** currently says *"Use fenced
  Markdown code blocks only for code, never for mathematics."* Diagrams are a third
  non-prose modality and this sentence has to account for them across all six system
  prompts that interpolate it.
- **`INTERLEAVE_INSTRUCTION` (`:11-23`)** defines the marker protocol and already needed
  the explicit guard *"Never put markers inside code fences"* because models got it wrong.
  Adding `{{diagram:N}}` will need the same care.

Require `alt_text` as a generated field, not an afterthought — it is both the accessibility
story and the PDF/degradation fallback.

---

## 6. Implementation plan

- **M0 — Mermaid validity check.** Format is decided (§3), so this is now narrower: 50
  diagrams, real prompts, **Mermaid × Luna vs Sol** (two cells). Measures (a) first-pass
  parser validity, (b) validity after one repair attempt, and (c) whether failures are
  **correlated** — the same construct failing repeatedly — or independent. Output gates the
  **model tier** (§4.7), and a bad enough result reopens the format decision. Whatever
  failure modes it surfaces go straight into the prompt manifest (§5).
- **M0.5 — svgdom spike (gating).** Prove or disprove browser-free rendering. With PlantUML
  no longer the fallback, there is no proven server-side render path in reserve except
  Puppeteer, so this must be settled before M3. Gates §4.5.
- **M1 — validator.** `node:20-slim` + mermaid + jsdom sandbox environment, long-lived
  process, invoked via the existing `run_script` path. Strip `%%{init:`. Unit-test the
  error-hash → feedback-string mapping.
- **M2 — generation job.** `diagram_build` job + table + gateway task, excluded from the
  lesson retry branch. Degrade-on-failure.
- **M3 — rendering.** `{{diagram:N}}` marker arm, sanitized SVG, PDF degradation.

---

## 7. Testing

- **Engine/validator (pure):** valid sources of each permitted type parse; the classic
  failures (unquoted parens) are caught; `<br>`, `&`, commas, emoji, curly quotes are
  *accepted*; `%%{init:` is stripped before parsing; error hash maps to a feedback string
  containing line, column, and expected tokens.
- **Failure isolation (the important one):** a lesson whose every diagram attempt fails
  still reaches `build_status='built'` with its prose and quiz intact, and does **not**
  consume `build_retry_count`. Model this on
  `services/worker/tests/test_lesson_build_retry.py:327-368`.
- **Security:** a diagram source attempting `htmlLabels` via `%%{init:` does not enable it;
  a source containing `<script>` does not produce executable output.
- **Backward compatibility:** existing v2 bundles with no diagrams render unchanged.

---

## 8. Risks and open questions

**Risks**

1. **Sanitization.** Adding a diagram renderer means either a sanitizer dependency (a new
   trust decision) or a hardened pre-render path. Either way this is a **security review
   item**, not a rendering detail — it would be the first `dangerouslySetInnerHTML` whose
   input derives from untrusted uploads.
2. **svgdom unproven** (§4.5). Falling back to Puppeteer materially changes the cost.
3. **Retry-budget multiplication.** Three bounded layers already compound (3 gateway × 3
   builder × 2 job retries) and none knows about the others. The separate-job design
   contains this; the inline alternative does not.
4. **Contract drift is unenforced.** `packages/contracts/schemas/lesson-bundle.schema.json`
   is documentation only — nothing loads it, no CI exists, and it has **already drifted**
   (it requires `\.py$` workspace paths while `lesson_schema.py` allows `.cpp/.h/.hpp`).
   `ARCHITECTURE.md` §7.2 is likewise stale at `schema_version: 1`. Budget the doc updates
   explicitly; nothing will remind you.
5. **Two renderers.** Web and PDF are independent implementations of the same grammar and
   already diverge on math.

**Open questions**

- Which diagram types to permit. Narrower is better for first-pass validity; the manifest
  is where this is enforced.
- Whether diagrams should be regenerable independently by the learner (the "regenerate
  lesson" path exists; a per-diagram equivalent may be cheap and useful).
- Whether a semantic-quality pass (LLM-as-judge on the rendered diagram) is worth it, or
  whether it inherits the epistemic-authority problem `PEDAGOGY_EVALUATION.md` §4.2 warns
  about.

**Non-goals**

- AI image generation (§2).
- Learner-authored or learner-edited diagrams.
- Interactive/animated diagrams.
- Semantic correctness guarantees.
