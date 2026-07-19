"use client";

import Link from "next/link";
import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import { PrerequisiteConcept, PrerequisiteRecommendation } from "@/lib/api";
import { Icon } from "@/components/icon";
import { MarkdownText } from "@/components/markdown-text";

// The relevant-track score for a prerequisite: applied code for a lab, conceptual
// understanding otherwise -- the same track that decided it was shaky.
function relevantPercent(prerequisite: PrerequisiteConcept): number | null {
  const value = prerequisite.kind === "coding" ? prerequisite.p_apply : prerequisite.p_understand;
  return value === null ? null : Math.round(value * 100);
}

// The reactive counterpart to PrerequisiteReview's page-load banner: shown the moment a graded
// answer or submission comes back flagged as "struggling", pointing at the shaky prerequisites
// the current concept builds on. The parent renders it only when a recommendation is present,
// so this component always has something to say.
export function PrerequisiteNudge({ courseId, recommendation }: { courseId: string; recommendation: PrerequisiteRecommendation }) {
  return (
    <Alert severity="warning" icon={<Icon name="account_tree" />} sx={{ display: "grid", gap: 1 }}>
      <AlertTitle sx={{ fontWeight: 700, mb: 0 }}>Stuck? Try reviewing this first</AlertTitle>
      <MarkdownText>{recommendation.reason_markdown}</MarkdownText>
      <Stack sx={{ gap: 1, mt: 0.5 }}>
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
