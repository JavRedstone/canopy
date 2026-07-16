import { CourseDetail } from "@/components/course-detail";

export default async function CoursePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <div className="shell">
      <CourseDetail courseId={id} />
    </div>
  );
}
