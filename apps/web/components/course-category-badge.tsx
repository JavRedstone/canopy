import { Icon } from "@/components/icon";
import { getCourseCategory } from "@/lib/course-category";

export function CourseCategoryBadge({ title, goal }: { title: string; goal: string }) {
  const category = getCourseCategory(title, goal);
  return (
    <span className="course-category-badge" style={{ background: category.color }}>
      <Icon name={category.icon} />
    </span>
  );
}
