"use client";

import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Paper from "@mui/material/Paper";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import { alpha } from "@mui/material/styles";
import { CourseMasteryResponse, getCourseMastery } from "@/lib/api";
import { MasteryMeter } from "@/components/mastery-meter";
import { Icon } from "@/components/icon";
import { conceptKindIcon } from "@/lib/concept-kind";
import { createClient } from "@/lib/supabase/client";

// A course-level "instrument panel": the continuous BKT estimate for every assessable
// concept, distinct from the coarse completion/points chip in the header. Refreshes when
// `refreshKey` changes so it can be nudged after the learner finishes a lesson.
export function MasteryDashboard({ courseId, refreshKey }: { courseId: string; refreshKey?: number }) {
  const [mastery, setMastery] = useState<CourseMasteryResponse>();
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const { data } = await createClient().auth.getSession();
      if (!data.session) return;
      try {
        const response = await getCourseMastery(courseId, data.session.access_token);
        if (!cancelled) {
          setMastery(response);
          setState("ready");
        }
      } catch {
        if (!cancelled) setState("error");
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [courseId, refreshKey]);

  if (state === "loading") {
    return (
      <Stack direction="row" sx={{ alignItems: "center", gap: 1, color: "text.secondary", py: 1 }}>
        <CircularProgress size={14} /> <Typography variant="body2">Loading mastery…</Typography>
      </Stack>
    );
  }
  if (state === "error" || !mastery || mastery.concepts.length === 0) return null;

  const total = mastery.concepts.length;
  const mastered = mastery.concepts.filter((concept) => concept.mastered).length;
  const pct = total > 0 ? Math.round((mastered / total) * 100) : 0;

  return (
    <Stack component="section" sx={{ gap: 2, mb: 3 }}>
      <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
        <Stack direction="row" sx={{ alignItems: "center", gap: 1 }}>
          <Icon name="insights" />
          <Box>
            <Typography sx={{ fontWeight: 700 }}>Mastery</Typography>
            <Typography variant="body2" color="text.secondary">
              Concept-level understanding vs. applied skill — tracked continuously, not just done/not-done.
            </Typography>
          </Box>
        </Stack>
        <Chip
          icon={<Icon name="verified" />}
          color={mastered === total ? "success" : "default"}
          variant={mastered === total ? "filled" : "outlined"}
          label={`${mastered} / ${total} mastered`}
        />
      </Stack>

      <Box sx={{ position: "relative", height: 8, borderRadius: 999, bgcolor: "action.hover", overflow: "hidden" }}>
        <Box sx={{ position: "absolute", insetBlock: 0, left: 0, width: `${pct}%`, borderRadius: 999, bgcolor: "success.main", transition: "width .5s cubic-bezier(.2,.8,.2,1)" }} />
      </Box>

      <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
        {mastery.concepts.map((concept) => (
          <Paper
            key={concept.slug}
            variant="outlined"
            sx={{ p: 1.75, display: "grid", gap: 1.25, borderColor: (theme) => (concept.mastered ? alpha(theme.palette.success.main, 0.6) : "divider") }}
          >
            <Stack direction="row" sx={{ alignItems: "center", gap: 1, minWidth: 0 }}>
              <Icon name={concept.mastered ? "verified" : conceptKindIcon(concept.kind)} />
              <Typography variant="body2" sx={{ fontWeight: 600, flex: 1, minWidth: 0 }} noWrap title={concept.title}>
                {concept.title}
              </Typography>
            </Stack>
            <MasteryMeter concept={concept} threshold={mastery.threshold} />
          </Paper>
        ))}
      </Box>
    </Stack>
  );
}
