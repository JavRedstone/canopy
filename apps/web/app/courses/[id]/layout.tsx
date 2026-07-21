import { CourseOutlineProvider } from "@/components/course-outline";

/** Exists so the course outline survives concept-to-concept navigation -- see
 *  CourseOutlineProvider's comment. */
export default async function CourseLayout({ params, children }: LayoutProps<"/courses/[id]">) {
  const { id } = await params;

  return <CourseOutlineProvider courseId={id}>{children}</CourseOutlineProvider>;
}
