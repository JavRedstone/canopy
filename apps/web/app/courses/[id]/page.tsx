import { CourseDetail } from "@/components/course-detail";
import { PageShell } from "@/components/page-shell";

export default async function CoursePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <PageShell>
      <CourseDetail courseId={id} />
    </PageShell>
  );
}
