# Recording scenes

Shot list derived from [RECORDING_SCRIPT.md](./RECORDING_SCRIPT.md). Record these clips,
in order, then assemble/voice-over to match the timings below.

## Pre-recording checklist

- [ ] Prepared course loaded, sourced from "Attention Is All You Need"
- [ ] Course goal set to: "Understand, implement, and reproduce the Transformer
      architecture from Attention Is All You Need."
- [ ] **Transformer block implementation** lab set up to fail once, then pass after a
      small fix
- [ ] Course has a cited lesson, mastery data, and a prerequisite recommendation ready
- [ ] Docker, worker, sandbox runner, API, gateway, and web app all running
- [ ] One real Codex-assisted diff or test result ready to show
- [ ] Dev-only auto-complete dialog disabled/hidden (test utility, keep out of frame)

## Recording order

Grouped into batches by app state, since some shots destroy the state the previous shot
needed (e.g. the lab can't be "failing" again once you've applied the fix). Each shot is
tagged with `→ video ⟨timestamp⟩`, its position in the final edit, so you can re-sequence
during assembly.

### Batch 1 — Static/prepared assets (no live app needed, get these out of the way first)

1. **Original paper view** → video 0:00-0:30
   The "Attention Is All You Need" paper on screen.

2. **Failed implementation attempt (prepared)** → video 0:00-0:30
   A prepared failed implementation attempt, shown as contrast to the paper.

3. **Codex-assisted diff or test result** → video 2:25-2:45
   One real Codex-assisted repository diff or test result, shown as engineering proof.

4. **Final slide** → video 2:45-3:00
   Closing slide/screen for the outro narration.

### Batch 2 — Create the course (must happen before it has modules)

5. **New Course creation** → video 0:30-0:50
   The New Course flow, showing the source input and the learner goal being entered.
   Do this first in the live app — everything after depends on the course existing.

### Batch 3 — Tour the generated course

6. **Prepared course modules overview** → video 0:50-1:35
   Full module list/progression: paper thesis and Transformer fundamentals → core
   components and training details → experiments and reproduction.

7. **Scaled dot-product attention lesson** → video 0:50-1:35
   Open the lesson and its source reference, showing the link back to the original paper.

### Batch 4 — Lab, failing state (shoot before touching the fix — this state is one-shot)

8. **Transformer block implementation lab — failing run** → video 0:50-1:35
   Open the lab, run the incomplete implementation, pause briefly on the failure output.
   Don't apply the fix yet — once fixed, this shot can't be redone without resetting.

### Batch 5 — Lab, fix and passing state (continuation of Batch 4, same session)

9. **Learning helper — hint and fix** → video 0:50-1:35
   Open the Learning helper, click **Give me a hint**, apply the small fix, rerun to a
   passing result.

10. **Passing lab / validation state** → video 2:25-2:45
    Clean re-open of the now-fixed lab for a tidy passing shot. Can reuse the rerun from
    the previous shot instead if it's clean enough.

### Batch 6 — Mastery and prerequisite data (needs evidence from the lab run to exist)

11. **Mastery dashboard — overview** → video 1:35-2:00
    The mastery dashboard for the course.

12. **Mastery dashboard — Understand vs. Apply signals** → video 1:35-2:00
    Close-up on the separate **Understand** and **Apply** scores for the Transformer
    course.

13. **Prerequisite recommendation** → video 2:00-2:25
    The triggered prerequisite recommendation after a struggle signal, showing the
    targeted concept to review.

## Fallback shots (record as backups)

- [ ] Prepared course ready to swap in immediately if live generation is slow
- [ ] Saved passing-lab result to show if Docker is unavailable (no live run)
- [ ] Separate Understand/Apply values ready to show if the prerequisite recommendation
      isn't available
