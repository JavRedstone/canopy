import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { CanopyBlobs } from "@/components/canopy-blobs";
import { NewCourseForm } from "@/components/new-course-form";
import { PageShell } from "@/components/page-shell";

// A single-task page, so the column is centred rather than pinned to the left of the shared
// reading width, which otherwise left most of a wide screen empty.
export default function NewCoursePage() {
  return (
    <PageShell>
      <Breadcrumbs items={[{ label: "My courses", href: "/courses" }, { label: "New course" }]} />
      {/* Same foliage wash as the landing hero, so creating a course feels like part of the
          same product rather than a bare admin form. */}
      <Box sx={{ position: "relative", pb: 4 }}>
        <CanopyBlobs />
      <Box sx={{ maxWidth: 620, mx: "auto", position: "relative", zIndex: 1 }}>
        <Box sx={{ textAlign: "center", mb: 4 }}>
          <Typography variant="overline" color="text.secondary">New canonical course</Typography>
          <Typography variant="h4" sx={{ letterSpacing: "-0.02em", my: 0.5 }}>Start with what you want to learn.</Typography>
          <Typography color="text.secondary">
            Your goal shapes the course. Add files or pasted text when you want it grounded in specific material.
          </Typography>
        </Box>
        <NewCourseForm />
      </Box>
      </Box>
    </PageShell>
  );
}
