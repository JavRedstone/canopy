import Link from "next/link";
import { LoginForm } from "@/components/login-form";

export default function LoginPage() {
  return (
    <main className="shell">
      <nav className="nav"><Link className="brand" href="/">Canopy</Link></nav>
      <section className="hero" style={{ maxWidth: 480 }}>
        <span className="eyebrow">Welcome</span>
        <h1>Start with your source material.</h1>
        <p>Use a passwordless sign-in link to keep your courses and documents private.</p>
        <LoginForm />
      </section>
    </main>
  );
}
