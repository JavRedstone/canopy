# Pedagogy evaluation — Canopy against the learning-science literature

**Status:** Analysis, not a spec. Directional input for product/curriculum decisions.
**Date:** 2026-07-18
**Method:** Canopy's teaching model (built + planned) evaluated against primary
education-research sources and meta-analyses. Every claim below carries an author-year
citation; the full reference list is at the end. Where a finding is contested, it says so.
**Related:** [`IDEA.md`](./IDEA.md) (product intent), [`../architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md)
(system design), [`USE_CASES.md`](./USE_CASES.md) (built vs planned, verified against code).

---

## 1. What "how Canopy teaches" actually means

Canopy's pedagogy is a stack of well-known moves:

- **Source-grounded generated lessons + worked examples** (read mode).
- **Embedded retrieval quizzes** — the `understand` mastery track.
- **Hands-on coding labs** with a run/submit loop and hidden tests — the `apply` track.
- **Per-concept dual-track Bayesian Knowledge Tracing (BKT)** driving a mastery dashboard.
- **A prerequisite concept graph** that flags weak prerequisites before a lesson.

**Built vs aspirational — read this before the evaluation.** The headline
differentiator, "the course reshapes itself around your mastery," is mostly still on
paper. Verified against the code:

- **Built:** dual-track BKT (`understand` from quizzes, `apply` from coding submissions),
  run/submit split, the mastery dashboard, prerequisite-review flagging
  (`REVIEW_THRESHOLD = 0.6`), and a struggle-triggered prerequisite *nudge* that is the
  first writer of `adaptation_events`.
- **Not built (or write-only):** nothing yet *consumes* `adaptation_events` — remediation
  lessons are not generated, the LLM diagnosis layer, transfer-check exercises,
  per-test concept tagging (the Q-matrix), the "works-but-fragile" visible-pass/hidden-fail
  signal, and the acceleration/support-signal rules are all unbuilt.

So today the system **measures** mastery and **nudges** (prerequisite review); it does
not yet **reshape** around mastery. This matters because several of Canopy's strongest
research-backed claims live entirely in the unbuilt half — which is also where they are
cheapest to get right.

---

## 2. Calibrate expectations first

The realistic ceiling for this class of system is **not** Bloom's 2σ. That 1984 result
was confounded — the tutoring arms were held to a 90% mastery threshold vs 80% in the
classroom arms, so "goal level" was not held constant — and it has never replicated at
that magnitude (Bloom 1984; see critique in VanLehn 2011).

The sober numbers:

- **Mastery learning:** d ≈ 0.52 (Kulik, Kulik & Bangert-Drowns 1990); near-zero on
  standardized tests under stricter controls (Slavin 1987).
- **Step-based intelligent tutoring:** d ≈ 0.76 in controlled studies — statistically
  indistinguishable from human tutors at d ≈ 0.79 (VanLehn 2011).
- **The field reality:** those lab effects collapse to **d ≈ 0.20 in large real-world
  trials, and only after a year of implementation maturity** (Pane et al. 2014, Cognitive
  Tutor Algebra at scale, RAND).

**Honest promise:** "meaningfully better than a chatbot and better than passive video,"
not "2 sigma."

---

## 3. What the research says Canopy gets right

**3.1 Learning-by-doing is the best-supported core it could have picked.**
Freeman et al. (2014, *PNAS*, 225 studies) found active learning raises exam performance
**+0.47 SD** and cuts failure rates from 34% to 22% (odds ratio 1.95 for failing under
lecture). Chi & Wylie's ICAP framework (2014) ranks *constructive/interactive* activity —
the learner generating output beyond what was presented — as the highest-yield mode. "Fill
in this function and run it against tests" sits squarely there. This is the least
contestable thing about the design.

**3.2 Retrieval-practice quizzes are on solid ground.** The testing effect is among the
most replicated findings in the field: Roediger & Karpicke (2006); Rowland (2014)
meta-analysis **g ≈ 0.50** vs restudy; Adesope, Trevisan & Sundararajan (2017)
**g ≈ 0.51**. Notably, re-readers are the *most confident and worst-performing* group — the
exact "illusion of mastery" a mastery-tracking system should want to puncture.

**3.3 Worked examples are correct — for novices.** Sweller & Cooper (1985) and Barbieri
et al. (2023, **d ≈ 0.48**) support front-loading worked examples in early skill
acquisition, which is what Canopy's lesson bundles do.

**3.4 Mastery-over-completion is directionally right.** Kulik et al. (1990) put mastery
learning at d ≈ 0.52 with *larger gains for weaker learners*. Canopy's tight
run→feedback→retry loop is the step-based interaction VanLehn (2011) found effective.

**3.5 Several choices are more sophisticated than typical edtech:**
- **Splitting `understand` (quiz) from `apply` (code)** aligns with the finding that you
  must assess at the cognitive level you care about — factual quizzing doesn't reliably
  transfer to higher-order skill (Agarwal et al. 2019). Collapsing them into one score, as
  completion-based tools do, would hide exactly the gap that matters.
- **Not penalizing help-seeking** (hints recorded as support level, never docked from
  mastery) avoids punishing the productive behavior.
- **Diagnosis framed as an evidence-backed, probe-verified hypothesis about code
  behavior** — not a claim about the learner's mind — is epistemically honest and rare.
- **Immutable observation ledger + interpretable BKT** supports transparency and
  self-regulated learning: the learner can see *why* the system believes what it does.
- **The self-validating sandbox** (reference solution must pass before a learner sees the
  lesson) directly addresses the biggest liability of generated content (§4.5).

**3.6 Source-grounding beats ungrounded chatbots.** RAG measurably reduces hallucination
versus free generation (Ayala & Bechard 2024), and grounding in *the learner's own*
materials gives correct terminology and citeable provenance. Against a plain
ChatGPT/NotebookLM baseline, this is a real pedagogical and trust advantage.

---

## 4. Where the research says Canopy falls short

**4.1 No spacing. The single clearest, best-quantified weakness.**
Canopy marks a concept "mastered" at `p ≥ 0.95` and never schedules it again. Standard
BKT literally has **no forgetting parameter** (Khajah, Lindsey & Mozer 2016) — once a skill
flips to "learned," it stays learned. But the durability evidence is overwhelming and
quantitative: spaced practice beats massed by **~15%** (Cepeda et al. 2006, 317
experiments); an immediate mass-study advantage *inverts within a week* (Roediger &
Karpicke 2006); stopping at an initial mastery criterion "leaves most durable retention on
the table" (Rawson & Dunlosky 2011). Canopy's mastery meter optimizes the *5-minute*
number and calls it done. **Adding spaced re-retrieval of mastered concepts is the
highest-confidence improvement available, and it reuses the quiz engine already built.**

**4.2 The `0.95` threshold and BKT are shakier than the dashboard implies.**
The cutoff is a 1994 convention (Corbett & Anderson 1994), not an empirically derived line.
BKT suffers documented **degeneracy** (Baker, Corbett & Aleven 2008 — unconstrained fits
imply "knowing the skill makes you answer *wrong* more often") and **identifiability**
concerns (Beck & Chang 2007, partly walked back by Doroudi & Brunskill 2017). Canopy's
specific problem is worse than the generic critique: it cold-starts from *conservative
priors, not data-fit parameters*, and uses one concept per lesson with **no per-item
Q-matrix**. So the early mastery percentages rendered as calibrated probabilities are
effectively priors with a thin layer of evidence on top. "78% applied mastery" carries more
epistemic authority in the UI than the model can support.

**4.3 "Scaffold after 2 failed attempts" substitutes a constant for what must be adaptive.**
This is the **assistance dilemma** (Koedinger & Aleven 2007) — an acknowledged *unsolved*
problem. Productive-failure work shows struggling *before* being rescued improves
conceptual and transfer outcomes (Sinha & Kapur 2021, **g ≈ 0.36** on conceptual/transfer,
~0 on procedural), and Warshauer (2015) finds the reflex to "show students what to do next"
is associated with *lower* conceptual gains. A fixed 2-strike trigger can short-circuit
productive struggle for a capable learner making progress. The complication: for genuine
novices on complex content, unresolved struggle becomes *unproductive* overload and earlier
help is correct (Ashman, Kalyuga & Sweller 2020). The evidence-aligned design is a trigger
sensitive to *learner level and whether the failure is productive* — not a flat count. The
count itself is the weak part, and since this loop is unbuilt, it is cheap to fix now.

**4.4 Generic MCQ is the weakest retrieval lever, and auto-generated items skew shallow.**
Recognition/MCQ is the *lowest-yield* retrieval format (Rowland 2014, **g ≈ 0.36**) because
it minimizes generative effort, and factual quizzing doesn't reliably transfer upward
(Agarwal et al. 2019). Layer on LLM-item quality: in the largest field study, AI-generated
exam items matched human items on discrimination but were **systematically easier** (Isley
et al. 2025, Δβ ≈ −0.79), and health-professions reviews report MCQ error rates from <1% to
45% (PLOS ONE 2025). Canopy gates its `understand` track on exactly these items. They need
competitive distractors, conceptual (not recall) framing, and feedback on failed retrievals
to earn their place — none guaranteed by generation alone.

**4.5 Passing generated tests ≠ understanding.** Baker et al. (2004) showed students who
"game" tutoring systems learn **~two-thirds as much**, and gating progress on
auto-generated checks invites exactly that. Canopy's hidden tests, static analysis, and
(planned) transfer checks are the right mitigations — but the transfer check is unbuilt, and
even validated hidden tests can be satisfied by hardcoding or pattern-matching. Treating a
green suite as a clean mastery signal is the assumption most likely to inflate the numbers.

**4.6 A concept graph from one document is content structure, not a learning progression.**
Backward design says sequence should flow from goals and assessments, not a document's
exposition order (Wiggins & McTighe 2005); valid learning progressions require *empirical*
data on how learners develop and where they hold misconceptions (Duncan & Hmelo-Silver
2009); and expertise reversal means no single order is optimal for all learners (Kalyuga et
al. 2003). Canopy auto-extracts a prerequisite graph from source + goal and treats it as the
canonical "spine." That's a plausible scaffold, but it inherits the author's expert blind
spot and encodes reference order, not teaching order — presented with more pedagogical
authority than an extracted graph has earned.

**4.7 Citations build trust faster than they earn it.** Canopy leans on "see §4.2 of your
textbook" as a trust mechanism, but grounding is not a guarantee: leading legal RAG tools
still hallucinate 17–33% of the time (Magesh et al. 2024), and *correctness ≠ faithfulness* —
models cite sources that don't actually support the sentence in up to 57% of adversarial
cases (Wallat et al. 2024). A citation that *looks* grounded is not evidence the claim *is*
grounded. Not hypothetical here: the retrieval-ivfflat bug silently returned *no* grounding
while generation proceeded anyway — the exact failure mode the literature warns about,
already observed once in this codebase.

**4.8 The "transfer exercises" are near transfer, not far.** "Same concept, new API shape"
holds the knowledge domain constant and varies only surface form — Barnett & Ceci (2002)
classify this as *horizontal/near* transfer. That's genuinely worthwhile: near transfer is
where transfer actually succeeds. But it shouldn't be framed as broad generalization — far
transfer is meta-analytically near-zero (Sala et al. 2019; Gobet & Sala 2022) and would need
deliberate design (varied domains, self-explanation, principle extraction) Canopy doesn't
attempt.

**4.9 Nothing fades.** The frontend renders all worked examples statically and all hints at
once (hints are not progressive). Expertise reversal (Kalyuga et al. 2003) and feedback
research (Shute 2008; Van der Kleij, Feskens & Eggen 2015) converge: support that helps
novices becomes redundant and eventually *harmful* for stronger learners, and feedback
directiveness should decrease as competence grows. Canopy's support level is constant across
the learner's trajectory.

**4.10 It's a solo instrument, and solo self-paced learning has a motivation problem.**
Self-paced mastery's documented Achilles heel is procrastination and non-completion (the
PSI/Keller-plan literature); MOOC completion sits at 3–15% and hasn't budged in a decade
(Reich & Ruipérez-Valiente 2019). Self-Determination Theory (Ryan & Deci 2020) says durable
motivation needs autonomy, competence, *and relatedness* — Canopy serves autonomy well and
has no cohort/instructor/social layer at all (single-owner in the code), leaving relatedness
structurally unmet. Compounding it: learner control has a **near-zero average effect** and is
*worst for novices* (Karich, Burns & Maki 2014), and learners are poor self-assessors
(Kruger & Dunning 1999; Bjork, Dunlosky & Kornell 2013). The "defer this recommendation /
choose the concise explanation / skip the drill" controls are honest and humane, but the
evidence says they're unlikely to *improve outcomes* and may hurt the novices who most need
direction.

---

## 5. Bottom line

**The scorecard.** Canopy's *foundations* are the strongest interventions in the field —
active learning, retrieval practice, worked examples, immediate feedback, mastery framing —
and a few choices (dual-track mastery, evidence-backed diagnosis, the self-validating
sandbox, source grounding) are ahead of typical edtech. Its weaknesses cluster into two
families:

1. **Fixed constants where the evidence demands adaptivity** — a 2-failure trigger, static
   examples/hints, a hard 0.95 cutoff, one-shot mastery. Four separate literatures
   (assistance dilemma, expertise reversal, feedback directiveness, desirable difficulties)
   all converge on one principle: *optimal support is an interaction of the learner's current
   knowledge with the goal, and it must fade.* Canopy substitutes a constant at each point.

2. **Trusting generated artifacts more than they've earned** — extracted concept graphs as
   validated progressions, auto-generated MCQs as sound assessments, green test suites as
   clean mastery signals, citations as proof of grounding.

**Prioritized fixes (by evidence strength):**

| # | Fix | Why it ranks here |
|---|-----|-------------------|
| 1 | **Spaced re-retrieval of mastered concepts** | Highest-confidence, best-quantified benefit (Cepeda 2006 +15%; one-shot mastery is not durable). Reuses the quiz engine already built. |
| 2 | **Make the remediation trigger adaptive to learner level** | Assistance dilemma + productive failure. Cheap — the loop is unbuilt. |
| 3 | **Strengthen quiz items** — conceptual framing, competitive distractors, feedback on failed retrieval | MCQ is the weakest retrieval lever; generated items skew easy. |
| 4 | **Fade examples/hints/feedback with competence** | Expertise reversal; feedback directiveness research. |
| 5 | **Soften the mastery UI's epistemic authority** | Cold-start priors + missing Q-matrix make early percentages weaker than they look. |

---

## References

**Mastery learning & tutoring efficacy**
- Bloom, B. S. (1984). The 2 Sigma Problem. *Educational Researcher*, 13(6), 4–16.
- Kulik, C.-L. C., Kulik, J. A., & Bangert-Drowns, R. L. (1990). Effectiveness of Mastery Learning Programs: A Meta-Analysis. *Review of Educational Research*, 60(2), 265–299.
- Slavin, R. E. (1987). Mastery Learning Reconsidered. *Review of Educational Research*, 57(2), 175–213.
- VanLehn, K. (2011). The Relative Effectiveness of Human Tutoring, Intelligent Tutoring Systems, and Other Tutoring Systems. *Educational Psychologist*, 46(4), 197–221.
- Pane, J. F., Griffin, B. A., McCaffrey, D. F., & Karam, R. (2014). Effectiveness of Cognitive Tutor Algebra I at Scale. *Educational Evaluation and Policy Analysis*, 36(2), 127–144.

**Knowledge tracing / BKT**
- Corbett, A. T., & Anderson, J. R. (1994). Knowledge Tracing. *User Modeling and User-Adapted Interaction*, 4, 253–278.
- Beck, J. E., & Chang, K. (2007). Identifiability: A Fundamental Problem of Student Modeling. *UM 2007*, LNCS 4511, 137–146.
- Doroudi, S., & Brunskill, E. (2017). The Misidentified Identifiability Problem of BKT. *EDM 2017*.
- Baker, R. S. J. d., Corbett, A. T., & Aleven, V. (2008). More Accurate Student Modeling through Contextual Estimation of Slip and Guess. *ITS 2008*.
- Khajah, M., Lindsey, R. V., & Mozer, M. C. (2016). How Deep is Knowledge Tracing? *EDM 2016*.
- Neshaei, S. P., et al. (2024). Towards Modeling Learner Performance with Large Language Models. *EDM 2024*.

**Retrieval practice, worked examples, active learning**
- Roediger, H. L., & Karpicke, J. D. (2006). Test-Enhanced Learning. *Psychological Science*, 17(3), 249–255.
- Rowland, C. A. (2014). The Effect of Testing versus Restudy on Retention. *Psychological Bulletin*, 140(6), 1432–1463.
- Adesope, O. O., Trevisan, D. A., & Sundararajan, N. (2017). Rethinking the Use of Tests. *Review of Educational Research*, 87(3), 659–701.
- Karpicke, J. D., & Blunt, J. R. (2011). Retrieval Practice Produces More Learning than Elaborative Studying. *Science*, 331(6018), 772–775.
- Agarwal, P. K. (2019). Retrieval Practice & Bloom's Taxonomy. *Journal of Educational Psychology*, 111(2), 189–209.
- Sweller, J., & Cooper, G. A. (1985). The Use of Worked Examples. *Cognition and Instruction*, 2(1), 59–89.
- Kalyuga, S., Ayres, P., Chandler, P., & Sweller, J. (2003). The Expertise Reversal Effect. *Educational Psychologist*, 38(1), 23–31.
- Barbieri, C. A., et al. (2023). Meta-analysis of Worked Examples. *Educational Psychology Review*, 35, 9.
- Freeman, S., et al. (2014). Active Learning Increases Student Performance in STEM. *PNAS*, 111(23), 8410–8415.
- Chi, M. T. H., & Wylie, R. (2014). The ICAP Framework. *Educational Psychologist*, 49(4), 219–243.

**Difficulty, failure, spacing, transfer, feedback**
- Koedinger, K. R., & Aleven, V. (2007). Exploring the Assistance Dilemma. *Educational Psychology Review*, 19, 239–264.
- Kapur, M. (2008). Productive Failure. *Cognition and Instruction*, 26(3), 379–424.
- Sinha, T., & Kapur, M. (2021). When Problem Solving Followed by Instruction Works. *Review of Educational Research*, 91(5), 761–798.
- Ashman, G., Kalyuga, S., & Sweller, J. (2020). Problem-solving or Explicit Instruction. *Educational Psychology Review*, 32, 229–247.
- Warshauer, H. K. (2015). Productive Struggle in Middle School Mathematics. *Journal of Mathematics Teacher Education*, 18, 375–400.
- Bjork, R. A., & Bjork, E. L. (2011). Making Things Hard on Yourself, But in a Good Way. In *Psychology and the Real World*.
- Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T., & Rohrer, D. (2006). Distributed Practice in Verbal Recall Tasks. *Psychological Bulletin*, 132(3), 354–380.
- Rawson, K. A., & Dunlosky, J. (2011). Optimizing Schedules of Retrieval Practice. *Journal of Experimental Psychology: General*, 140(3), 283–302.
- Barnett, S. M., & Ceci, S. J. (2002). When and Where Do We Apply What We Learn? A Taxonomy for Far Transfer. *Psychological Bulletin*, 128(4), 612–637.
- Sala, G., et al. (2019). Near and Far Transfer in Cognitive Training. *Collabra: Psychology*, 5(1).
- Gobet, F., & Sala, G. (2022). Cognitive Training: A Field in Search of a Phenomenon. *Perspectives on Psychological Science*.
- Hattie, J., & Timperley, H. (2007). The Power of Feedback. *Review of Educational Research*, 77(1), 81–112.
- Kluger, A. N., & DeNisi, A. (1996). The Effects of Feedback Interventions. *Psychological Bulletin*, 119(2), 254–284.
- Shute, V. J. (2008). Focus on Formative Feedback. *Review of Educational Research*, 78(1), 153–189.
- Van der Kleij, F. M., Feskens, R. C. W., & Eggen, T. J. H. M. (2015). Effects of Feedback in a Computer-Based Learning Environment. *Review of Educational Research*, 85(4), 475–511.

**AI-generated content, RAG, personalization, motivation**
- Isley, P., Gilbert, T., Kassos, A., et al. (2025). Assessing the Quality of AI-Generated Exams: A Large-Scale Field Study. arXiv:2508.08314.
- *PLOS ONE* (2025). The Use of LLMs in Generating MCQs for Health Professions Education (systematic review + network meta-analysis).
- Ayala, O., & Bechard, P. (2024). Reducing Hallucination in Structured Outputs via RAG. *NAACL 2024 (Industry)*.
- Magesh, V., Surani, F., … Ho, D. E. (2024). Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools. *Journal of Empirical Legal Studies*.
- Wallat, J., Anand, A., et al. (2024). Correctness is not Faithfulness in RAG Attributions. arXiv:2412.18004.
- Wiggins, G., & McTighe, J. (2005). *Understanding by Design* (2nd ed.). ASCD.
- Duncan, R. G., & Hmelo-Silver, C. E. (2009). Learning Progressions. *Journal of Research in Science Teaching*, 46(6), 606–609.
- Karich, A. C., Burns, M. K., & Maki, K. E. (2014). Meta-Analysis of Learner Control. *Review of Educational Research*, 84(3), 392–410.
- Pashler, H., McDaniel, M., Rohrer, D., & Bjork, R. (2008). Learning Styles: Concepts and Evidence. *Psychological Science in the Public Interest*, 9(3), 105–119.
- Kruger, J., & Dunning, D. (1999). Unskilled and Unaware of It. *Journal of Personality and Social Psychology*, 77(6), 1121–1134.
- Bjork, R. A., Dunlosky, J., & Kornell, N. (2013). Self-Regulated Learning: Beliefs, Techniques, and Illusions. *Annual Review of Psychology*, 64, 417–444.
- Reich, J., & Ruipérez-Valiente, J. A. (2019). The MOOC Pivot. *Science*, 363(6423), 130–131.
- Ryan, R. M., & Deci, E. L. (2020). Intrinsic and Extrinsic Motivation from a Self-Determination Theory Perspective. *Contemporary Educational Psychology*, 61.

**Gaming the system**
- Baker, R. S. J. d., Corbett, A. T., Koedinger, K. R., & Wagner, A. Z. (2004). Off-Task Behavior in the Cognitive Tutor Classroom: When Students Game the System. *CHI 2004*.
