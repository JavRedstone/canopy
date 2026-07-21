import Image from "next/image";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { AppShell } from "@/components/app-shell";
import { CanopyBlobs } from "@/components/canopy-blobs";
import { LinkButton } from "@/components/link-button";
import { PageShell } from "@/components/page-shell";
import { SiteFooter } from "@/components/site-footer";
import { createClient } from "@/lib/supabase/server";

const DEMO_VIDEO_ID = "5FqJQYg25RM";

export default async function HomePage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  return (
    <AppShell email={user?.email}>
      {/* Wider than the app's 1040 reading column: the hero is a two-up composition rather
          than prose, and the extra width is what lets the 16:9 video stand as tall as the
          copy beside it. */}
      <PageShell maxWidth={1400}>
        <Box
          component="section"
          // No top padding of its own -- PageShell already supplies the gap under the header,
          // and stacking both left a conspicuous empty band above the hero.
          sx={{ position: "relative", pb: { xs: 6, md: 8 } }}
        >
          <CanopyBlobs />

          <Box
            sx={{
              position: "relative",
              zIndex: 1,
              display: "grid",
              gridTemplateColumns: { xs: "1fr", md: "1.45fr 1fr" },
              // Stretch rather than centre so the video ends up exactly as tall as the copy
              // column, instead of overhanging it at both ends.
              alignItems: { xs: "start", md: "stretch" },
              gap: { xs: 4, md: 5 }
            }}
          >
            <Box>
              <Typography variant="overline" color="text.secondary">Adaptive technical learning</Typography>
              <Typography
                component="h1"
                variant="h2"
                sx={{ fontSize: "clamp(2rem, 4vw, 2.75rem)", letterSpacing: "-0.02em", lineHeight: 1.1, my: 1.5 }}
              >
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
              aria-label="Product demo"
              sx={{
                position: "relative",
                // Fixed ratio only while stacked; on md the stretched row sets the height.
                aspectRatio: { xs: "16 / 9", md: "auto" },
                borderRadius: 2,
                overflow: "hidden",
                border: 1,
                borderColor: "divider",
                bgcolor: "background.paper"
              }}
            >
              <Box
                component="iframe"
                // youtube-nocookie so an unplayed embed does not set tracking cookies on visitors.
                src={`https://www.youtube-nocookie.com/embed/${DEMO_VIDEO_ID}`}
                title="Canopy demo"
                allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowFullScreen
                sx={{ position: "absolute", inset: 0, width: "100%", height: "100%", border: 0 }}
              />
            </Box>
          </Box>

          <Box
            aria-label="How Canopy works"
            sx={{
              position: "relative",
              zIndex: 1,
              display: "grid",
              gap: 3,
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              mt: { xs: 5, md: 7 }
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
        </Box>

        <Box
          component="section"
          aria-labelledby="source-grounded-heading"
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", md: "minmax(260px, 0.72fr) minmax(0, 1.6fr)" },
            alignItems: "center",
            gap: { xs: 3, md: 5 },
            mb: { xs: 6, md: 8 },
            p: { xs: 2.5, sm: 3, md: 4 },
            border: 1,
            borderColor: "divider",
            borderRadius: 2,
            bgcolor: "background.paper",
            overflow: "hidden"
          }}
        >
          <Box sx={{ maxWidth: { md: 360 } }}>
            <Typography variant="overline" color="primary.main">
              Grounded in your material
            </Typography>
            <Typography
              id="source-grounded-heading"
              component="h2"
              variant="h4"
              sx={{ mt: 0.75, mb: 1.5, letterSpacing: "-0.015em" }}
            >
              See exactly where every lesson comes from.
            </Typography>
            <Typography color="text.secondary">
              Citations open the original source at the relevant passage, so explanations stay verifiable and your
              material remains the ground truth.
            </Typography>
          </Box>

          <Box
            sx={{
              lineHeight: 0,
              borderRadius: 1.5,
              overflow: "hidden",
              border: 1,
              borderColor: "divider",
              boxShadow: "0 18px 48px rgba(20, 34, 28, 0.14)",
              transform: { md: "rotate(0.35deg)" }
            }}
          >
            <Image
              src="/landing/source-grounded.png"
              alt="A Canopy lesson with a citation dialog open to the exact excerpt from the uploaded source PDF"
              width={1917}
              height={980}
              sizes="(max-width: 899px) calc(100vw - 72px), 60vw"
              style={{ width: "100%", height: "auto" }}
            />
          </Box>
        </Box>

        <Box
          component="section"
          aria-label="Product principles"
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            pt: 5,
            borderTop: 1,
            borderColor: "divider"
          }}
        >
          {[
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

        <Box sx={{ mt: { xs: 6, md: 8 } }}>
          <SiteFooter />
        </Box>
      </PageShell>
    </AppShell>
  );
}
