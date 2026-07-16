import Link from "next/link";
import { CourseDashboard } from "@/components/course-dashboard";

export default function CoursesPage() {
  return (
    <div className="shell">
      <header className="page-header"><div><span className="eyebrow">Learning library</span><h1>My courses</h1><p className="muted">Each course has its own source set, route, and mastery record.</p></div><Link className="button" href="/courses/new">New course</Link></header>
      <CourseDashboard />
    </div>
  );
}
