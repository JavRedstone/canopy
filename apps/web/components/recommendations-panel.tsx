"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Paper from "@mui/material/Paper";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import { alpha } from "@mui/material/styles";
import { PrerequisiteConcept, RecommendationDecision, RecommendationSummary, decideRecommendation, getCourseRecommendations } from "@/lib/api";
import { Icon } from "@/components/icon";
import { createClient } from "@/lib/supabase/client";

// The relevant-track score for a prerequisite: applied code for a lab, understanding otherwise
// -- the same track that decided it was shaky.
function relevantPercent(prerequisite: PrerequisiteConcept): number | null {
  const value = prerequisite.kind === "coding" ? prerequisite.p_apply : prerequisite.p_understand;
  return value === null ? null : Math.round(value * 100);
}

// The course-level counterpart to the inline struggle nudge: every open prerequisite-review
// recommendation the learner has accrued, each actionable. "Review now" commits (accepted) and
// jumps to the weakest prerequisite; "Later" defers; "Dismiss" declines. Acting on one resolves
// its adaptation_event server-side and drops it from the list. Renders nothing when empty.
export function RecommendationsPanel({ courseId }: { courseId: string }) {
  const router = useRouter();
  const [items, setItems] = useState<RecommendationSummary[]>([]);
  const [busyId, setBusyId] = useState<string>();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const { data } = await createClient().auth.getSession();
      if (!data.session) return;
      try {
        const response = await getCourseRecommendations(courseId, data.session.access_token);
        if (!cancelled) setItems(response.recommendations);
      } catch {
        // Non-fatal: the panel just stays hidden if recommendations can't be loaded.
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  async function decide(recommendation: RecommendationSummary, decision: RecommendationDecision, reviewSlug?: string) {
    setBusyId(recommendation.id);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      await decideRecommendation(courseId, recommendation.id, decision, data.session.access_token);
      setItems((current) => current.filter((entry) => entry.id !== recommendation.id));
      if (reviewSlug) router.push(`/courses/${courseId}/concepts/${reviewSlug}`);
    } catch {
      // Leave the recommendation in place so the learner can retry the action.
    } finally {
      setBusyId(undefined);
    }
  }

  if (items.length === 0) return null;

  return (
    <Paper
      component="section"
      variant="outlined"
      sx={{
        p: 2.5,
        mb: 3,
        borderRadius: 2,
        borderColor: (theme) => alpha(theme.palette.warning.main, 0.5),
        bgcolor: (theme) => alpha(theme.palette.warning.main, 0.04),
      }}
    >
      <Stack sx={{ gap: 2 }}>
        <Stack direction="row" sx={{ alignItems: "center", gap: 1.25 }}>
          <Box
            sx={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              display: "grid",
              placeItems: "center",
              color: "warning.main",
              bgcolor: (theme) => alpha(theme.palette.warning.main, 0.15),
              "& .material-symbol": { fontSize: "18px" },
            }}
          >
            <Icon name="account_tree" />
          </Box>
          <Box>
            <Typography sx={{ fontWeight: 700 }}>Recommended reviews</Typography>
            <Typography variant="body2" color="text.secondary">
              You&apos;ve been struggling on {items.length === 1 ? "a concept" : `${items.length} concepts`}. Reviewing what
              {items.length === 1 ? " it builds" : " they build"} on should help it click.
            </Typography>
          </Box>
        </Stack>

        {items.map((recommendation) => {
          const weakest = recommendation.prerequisites[0];
          const acting = busyId === recommendation.id;
          return (
            <Paper key={recommendation.id} variant="outlined" sx={{ p: 2, display: "grid", gap: 1.25 }}>
              <Typography variant="body2">
                <Box component="strong" sx={{ fontWeight: 700 }}>{recommendation.concept_title}</Box> builds on:
              </Typography>
              <Stack sx={{ gap: 0.75 }}>
                {recommendation.prerequisites.map((prerequisite) => {
                  const percent = relevantPercent(prerequisite);
                  return (
                    <Stack
                      key={prerequisite.slug}
                      direction="row"
                      sx={{ alignItems: "center", justifyContent: "space-between", gap: 1, flexWrap: "wrap" }}
                    >
                      <Stack direction="row" sx={{ alignItems: "center", gap: 1, minWidth: 0 }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }} noWrap title={prerequisite.title}>
                          {prerequisite.title}
                        </Typography>
                        {percent !== null ? (
                          <Chip
                            size="small"
                            variant="outlined"
                            label={`${percent}% ${prerequisite.kind === "coding" ? "apply" : "understand"}`}
                            sx={{ fontVariantNumeric: "tabular-nums" }}
                          />
                        ) : null}
                      </Stack>
                      <Button
                        component={Link}
                        href={`/courses/${courseId}/concepts/${prerequisite.slug}`}
                        size="small"
                        variant="text"
                        color="inherit"
                        endIcon={<Icon name="arrow_forward" />}
                      >
                        Open
                      </Button>
                    </Stack>
                  );
                })}
              </Stack>
              <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap", mt: 0.5 }}>
                <Button
                  variant="contained"
                  size="small"
                  disabled={acting || !weakest}
                  onClick={() => decide(recommendation, "accepted", weakest?.slug)}
                  startIcon={<Icon name="play_arrow" />}
                >
                  Review now
                </Button>
                <Button variant="outlined" size="small" color="inherit" disabled={acting} onClick={() => decide(recommendation, "deferred")}>
                  Later
                </Button>
                <Button variant="text" size="small" color="inherit" disabled={acting} onClick={() => decide(recommendation, "declined")}>
                  Dismiss
                </Button>
              </Stack>
            </Paper>
          );
        })}
      </Stack>
    </Paper>
  );
}
