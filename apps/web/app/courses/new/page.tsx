import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { NewCourseForm } from "@/components/new-course-form";
import { PageShell } from "@/components/page-shell";

export default function NewCoursePage() {
  return (
    <PageShell>
      <Breadcrumbs items={[{ label: "My courses", href: "/courses" }, { label: "New course" }]} />
      <Box sx={{ maxWidth: 560 }}>
        <Typography variant="overline" color="text.secondary">New canonical course</Typography>
        <Typography variant="h4" sx={{ letterSpacing: "-0.02em", my: 0.25 }}>Start with what you want to learn.</Typography>
        <Typography color="text.secondary">
          Your goal shapes the course. Add files or pasted text when you want the course grounded in specific material.
        </Typography>
        <NewCourseForm />
      </Box>
    </PageShell>
  );
}
