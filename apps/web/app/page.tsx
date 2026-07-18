import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { SignOutButton } from "@/components/sign-out-button";
import { BrandLink } from "@/components/brand-link";
import { LinkButton } from "@/components/link-button";
import { PageShell } from "@/components/page-shell";
import { createClient } from "@/lib/supabase/server";

export default async function HomePage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  return (
    <PageShell>
      <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", gap: 3, mb: 7 }}>
        <BrandLink size="large" />
        {user ? (
          <Stack direction="row" sx={{ alignItems: "center", gap: 2 }}>
            <Typography color="text.secondary">{user.email}</Typography>
            <SignOutButton />
          </Stack>
        ) : (
          <LinkButton href="/login" variant="outlined">Sign in</LinkButton>
        )}
      </Stack>

      <Box sx={{ maxWidth: 680 }}>
        <Typography variant="overline" color="text.secondary">Adaptive technical learning</Typography>
        <Typography variant="h2" sx={{ fontSize: "clamp(2rem, 5vw, 3rem)", letterSpacing: "-0.02em", lineHeight: 1.1, my: "12px" }}>
          Turn your own documents into a hands-on coding course.
        </Typography>
        <Typography color="text.secondary" sx={{ fontSize: "1.05rem" }}>
          Upload documentation, papers, or notes. Canopy generates a source-grounded course: lessons, exercises,
          and tests cited back to the material they came from. It reshapes your route as you learn, without ever
          rewriting what you have already completed.
        </Typography>
        <LinkButton href="/courses" variant="contained" size="large" sx={{ mt: 3 }}>Open your courses</LinkButton>
      </Box>

      <Box
        component="section"
        aria-label="How Canopy works"
        sx={{
          display: "grid",
          gap: 3,
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          mt: 8,
          pt: 5,
          borderTop: 1,
          borderColor: "divider"
        }}
      >
        {[
          { title: "Upload a source", body: "A PDF, a Markdown file, or plain notes become the ground truth for every lesson Canopy generates." },
          { title: "Get a generated course", body: "A canonical concept map of lessons and coding exercises, each one citing the section it was grounded in." },
          { title: "Practice in a live sandbox", body: "A code editor and terminal run each exercise in the browser. Run tests freely while you work, then submit when you are ready for it to count." },
          { title: "It adapts to you", body: "Struggle on a concept and Canopy inserts a targeted refresher; move fast and it keeps pace. Every change is visible and explained, never silent." }
        ].map((step, index) => (
          <Box component="article" key={step.title}>
            <Box
              sx={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 28,
                height: 28,
                borderRadius: "999px",
                bgcolor: "primary.main",
                color: "primary.contrastText",
                fontSize: "0.8rem",
                fontWeight: 700,
                mb: 1.5
              }}
            >
              {index + 1}
            </Box>
            <Typography variant="h6" sx={{ mb: 0.75 }}>{step.title}</Typography>
            <Typography variant="body2" color="text.secondary">{step.body}</Typography>
          </Box>
        ))}
      </Box>

      <Box
        component="section"
        aria-label="Product principles"
        sx={{ display: "grid", gap: 2, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", mt: 5 }}
      >
        {[
          { title: "Source-grounded", body: "Every explanation and exercise cites the exact section of your material it was generated from." },
          { title: "Mastery, not completion", body: "Tracks what you understand versus what you can apply, concept by concept, not just whether you clicked next." },
          { title: "Trustworthy by construction", body: "Every exercise validates itself against its own tests before you ever see it." }
        ].map((card) => (
          <Box
            component="article"
            key={card.title}
            sx={{ border: 1, borderColor: "divider", borderRadius: 1.5, bgcolor: "background.paper", p: 2.5 }}
          >
            <Typography variant="subtitle1" sx={{ mb: 1 }}>{card.title}</Typography>
            <Typography variant="body2" color="text.secondary">{card.body}</Typography>
          </Box>
        ))}
      </Box>
    </PageShell>
  );
}
