"use client";

import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Tooltip from "@mui/material/Tooltip";
import Chip from "@mui/material/Chip";
import Paper from "@mui/material/Paper";
import { alpha } from "@mui/material/styles";
import { Icon } from "@/components/icon";
import type { ConceptMastery } from "@/lib/api";

// A single BKT track rendered as a labelled bar with a marker at the mastery threshold, so
// the learner sees both where they are and how far the 95% bar is. `p === null` means the
// track has no observations yet -- shown as an empty bar with an em dash, never a false 0%.
function TrackBar({ label, hint, p, opportunities, threshold }: { label: string; hint: string; p: number | null; opportunities: number; threshold: number }) {
  const hasData = p !== null;
  const pct = hasData ? Math.round(p * 100) : 0;
  const mastered = hasData && p >= threshold;
  return (
    <Stack sx={{ gap: 0.5 }}>
      <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "baseline", gap: 1 }}>
        <Tooltip title={hint} placement="top-start">
          <Typography variant="caption" sx={{ color: "text.secondary", cursor: "help" }}>{label}</Typography>
        </Tooltip>
        <Typography variant="caption" sx={{ fontWeight: 700, fontVariantNumeric: "tabular-nums", color: mastered ? "success.main" : hasData ? "text.primary" : "text.disabled" }}>
          {hasData ? `${pct}%` : "—"}
        </Typography>
      </Stack>
      <Box sx={{ position: "relative", height: 8, borderRadius: 999, bgcolor: "action.hover", overflow: "hidden" }}>
        <Box
          sx={{
            position: "absolute",
            insetBlock: 0,
            left: 0,
            width: `${pct}%`,
            borderRadius: 999,
            bgcolor: mastered ? "success.main" : "primary.main",
            transition: "width .5s cubic-bezier(.2,.8,.2,1)"
          }}
        />
        {/* The 95% mastery bar the learner is aiming to clear. */}
        <Box sx={{ position: "absolute", insetBlock: -1, left: `${Math.round(threshold * 100)}%`, width: "2px", bgcolor: (theme) => alpha(theme.palette.text.primary, 0.35) }} />
      </Box>
      <Typography variant="caption" sx={{ color: "text.disabled" }}>
        {opportunities === 0 ? "no attempts yet" : `${opportunities} observation${opportunities === 1 ? "" : "s"}`}
      </Typography>
    </Stack>
  );
}

const UNDERSTAND_HINT = "Recall & explanation, from quiz answers.";
const APPLY_HINT = "Implementing it in code, from your submissions.";

/** Whether each track is relevant for a concept: everything shows Understand; only coding
 *  labs show Apply. A coding lab that also quizzes still shows both. */
export function masteryTracks(concept: Pick<ConceptMastery, "kind" | "understand_opportunities" | "p_understand">) {
  return {
    understand: concept.kind !== "coding" || concept.understand_opportunities > 0 || concept.p_understand !== null,
    apply: concept.kind === "coding"
  };
}

export function MasteryMeter({ concept, threshold }: { concept: ConceptMastery; threshold: number }) {
  const tracks = masteryTracks(concept);
  return (
    <Stack sx={{ gap: 1.25 }}>
      {tracks.understand ? (
        <TrackBar label="Understand" hint={UNDERSTAND_HINT} p={concept.p_understand} opportunities={concept.understand_opportunities} threshold={threshold} />
      ) : null}
      {tracks.apply ? (
        <TrackBar label="Apply" hint={APPLY_HINT} p={concept.p_apply} opportunities={concept.apply_opportunities} threshold={threshold} />
      ) : null}
    </Stack>
  );
}

/** A titled card version of the meter for the lesson page: header + a "Mastered" chip once
 *  the concept clears the bar on every track it's assessed on. */
export function MasteryCard({ concept, threshold }: { concept: ConceptMastery; threshold: number }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, display: "grid", gap: 1.5, borderColor: concept.mastered ? "success.main" : "divider" }}>
      <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", gap: 1 }}>
        <Stack direction="row" sx={{ alignItems: "center", gap: 0.75 }}>
          <Icon name="insights" />
          <Typography variant="overline" color="text.secondary">Your mastery</Typography>
        </Stack>
        {concept.mastered ? <Chip size="small" color="success" variant="outlined" icon={<Icon name="verified" />} label="Mastered" /> : null}
      </Stack>
      <MasteryMeter concept={concept} threshold={threshold} />
    </Paper>
  );
}
