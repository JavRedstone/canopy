import Avatar from "@mui/material/Avatar";
import { Icon } from "@/components/icon";
import { getCourseCategory } from "@/lib/course-category";

export function CourseCategoryBadge({ title, goal }: { title: string; goal: string }) {
  const category = getCourseCategory(title, goal);
  return (
    <Avatar variant="rounded" sx={{ bgcolor: category.color, width: 36, height: 36, color: "text.primary", "& .material-symbol": { fontSize: 19, opacity: 0.75 } }}>
      <Icon name={category.icon} />
    </Avatar>
  );
}
