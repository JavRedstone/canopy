import Link from "next/link";
import { SignOutButton } from "@/components/sign-out-button";
import { createClient } from "@/lib/supabase/server";

export default async function HomePage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  return (
    <main className="shell">
      <nav className="nav">
        <span className="brand">Canopy</span>
        {user ? (
          <div className="nav-user"><span className="muted">{user.email}</span><SignOutButton /></div>
        ) : (
          <Link className="button button-secondary" href="/login">Sign in</Link>
        )}
      </nav>
      <section className="hero">
        <span className="eyebrow">Adaptive technical learning</span>
        <h1>Turn your own documents into a hands-on coding course.</h1>
        <p>
          Upload documentation, papers, or notes. Canopy generates a source-grounded course: lessons, exercises,
          and tests cited back to the material they came from. It reshapes your route as you learn, without ever
          rewriting what you have already completed.
        </p>
        <Link className="button" href="/courses">Open your courses</Link>
      </section>

      <section className="steps" aria-label="How Canopy works">
        <article className="step">
          <span className="step-number">1</span>
          <h2>Upload a source</h2>
          <p>A PDF, a Markdown file, or plain notes become the ground truth for every lesson Canopy generates.</p>
        </article>
        <article className="step">
          <span className="step-number">2</span>
          <h2>Get a generated course</h2>
          <p>A canonical concept map of lessons and coding exercises, each one citing the section it was grounded in.</p>
        </article>
        <article className="step">
          <span className="step-number">3</span>
          <h2>Practice in a live sandbox</h2>
          <p>A code editor and terminal run each exercise in the browser. Run tests freely while you work, then submit when you are ready for it to count.</p>
        </article>
        <article className="step">
          <span className="step-number">4</span>
          <h2>It adapts to you</h2>
          <p>Struggle on a concept and Canopy inserts a targeted refresher; move fast and it keeps pace. Every change is visible and explained, never silent.</p>
        </article>
      </section>

      <section className="card-grid" aria-label="Product principles">
        <article className="card">
          <h2>Source-grounded</h2>
          <p>Every explanation and exercise cites the exact section of your material it was generated from.</p>
        </article>
        <article className="card">
          <h2>Mastery, not completion</h2>
          <p>Tracks what you understand versus what you can apply, concept by concept, not just whether you clicked next.</p>
        </article>
        <article className="card">
          <h2>Trustworthy by construction</h2>
          <p>Every exercise validates itself against its own tests before you ever see it.</p>
        </article>
      </section>
    </main>
  );
}
