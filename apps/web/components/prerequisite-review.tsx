"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import { PrerequisiteConcept, PrerequisiteReviewResponse, getConceptPrerequisites } from "@/lib/api";
import { Icon } from "@/components/icon";
import { createClient } from "@/lib/supabase/client";

// The relevant-track score for a prerequisite: applied code for a lab, conceptual
// understanding otherwise -- the same track that decided it needed review.
function relevantPercent(prerequisite: PrerequisiteConcept): number | null {
  const value = prerequisite.kind === "coding" ? prerequisite.p_apply : prerequisite.p_understand;
  return value === null ? null : Math.round(value * 100);
}

// The prerequisite-review recommendation: when the concept graph says this lesson builds on
// concepts the learner has practiced but is shaky on, point them back to shore those up
// first. Renders nothing unless a real weakness is detected, so it never nags on a clean run.
export function PrerequisiteReview({ courseId, slug }: { courseId: string; slug: string }) {
  const [data, setData] = useState<PrerequisiteReviewResponse>();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const { data: session } = await createClient().auth.getSession();
      if (!session.session) return;
      try {
        const response = await getConceptPrerequisites(courseId, slug, session.session.access_token);
        if (!cancelled) setData(response);
      } catch {
        // Non-fatal: the lesson is still fully usable without the recommendation.
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [courseId, slug]);

  if (!data || !data.review_recommended) return null;
  const weak = data.prerequisites.filter((prerequisite) => prerequisite.needs_review);

  return (
    <Alert severity="warning" icon={<Icon name="account_tree" />} sx={{ display: "grid", gap: 1 }}>
      <AlertTitle sx={{ fontWeight: 700, mb: 0 }}>Review recommended first</AlertTitle>
      <Typography variant="body2">
        This builds on {weak.length === 1 ? "a concept" : "concepts"} you&apos;re still shaky on. A quick review will make it click faster.
      </Typography>
      <Stack sx={{ gap: 1, mt: 0.5 }}>
        {weak.map((prerequisite) => {
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
                size="small"
                variant="outlined"
                color="inherit"
                component={Link}
                href={`/courses/${courseId}/concepts/${prerequisite.slug}`}
                endIcon={<Icon name="arrow_forward" />}
              >
                Review
              </Button>
            </Stack>
          );
        })}
      </Stack>
    </Alert>
  );
}
