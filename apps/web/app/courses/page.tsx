import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { CourseDashboard } from "@/components/course-dashboard";
import { ImportCourseButton } from "@/components/course-import-dialog";
import { LinkButton } from "@/components/link-button";
import { PageShell } from "@/components/page-shell";

export default function CoursesPage() {
  return (
    <PageShell>
      <Stack direction="row" sx={{ alignItems: "flex-start", justifyContent: "space-between", gap: 3, mb: 4 }}>
        <Stack>
          <Typography variant="overline" color="text.secondary">Learning library</Typography>
          <Typography variant="h4" sx={{ letterSpacing: "-0.02em", my: 0.25 }}>My courses</Typography>
          <Typography color="text.secondary">Each course has its own source set, route, and mastery record.</Typography>
        </Stack>
        <Stack direction="row" sx={{ gap: 1.5 }}>
          <LinkButton href="/courses/playground" variant="outlined">Sandbox playground</LinkButton>
          <ImportCourseButton />
          <LinkButton href="/courses/new" variant="contained">New course</LinkButton>
        </Stack>
      </Stack>
      <CourseDashboard />
    </PageShell>
  );
}
