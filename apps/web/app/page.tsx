import Link from "next/link";

export default function HomePage() {
  return (
    <main className="shell">
      <nav className="nav">
        <span className="brand">SourceLab</span>
        <Link className="button-link button-secondary" href="/login">Sign in</Link>
      </nav>
      <section className="hero">
        <span className="eyebrow">Adaptive technical learning</span>
        <h1>Learn directly from the materials that matter to you.</h1>
        <p>
          Build canonical, source-grounded coding courses from your documentation, notes, and technical readings.
          Your learning route adapts; your course remains stable and reviewable.
        </p>
        <Link className="button-link" href="/courses">Open your courses</Link>
      </section>
      <section className="card-grid" aria-label="Product principles">
        <article className="card"><h2>Source-grounded</h2><p>Every explanation connects back to the material that informed it.</p></article>
        <article className="card"><h2>Hands-on</h2><p>Read, run code, submit work, and practice with focused labs.</p></article>
        <article className="card"><h2>Learner-controlled</h2><p>Recommendations explain themselves and never silently rewrite your course.</p></article>
      </section>
    </main>
  );
}
