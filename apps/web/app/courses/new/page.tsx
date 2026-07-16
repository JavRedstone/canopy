import { Breadcrumbs } from "@/components/breadcrumbs";
import { NewCourseForm } from "@/components/new-course-form";

export default function NewCoursePage() {
  return (
    <div className="shell">
      <Breadcrumbs items={[{ label: "My courses", href: "/courses" }, { label: "New course" }]} />
      <section className="hero" style={{ maxWidth: 560 }}>
        <span className="eyebrow">New canonical course</span>
        <h1>Start with what you want to learn.</h1>
        <p>Your goal shapes the course. Add files or pasted text when you want the course grounded in specific material.</p>
        <NewCourseForm />
      </section>
    </div>
  );
}
