import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { BrandLink } from "@/components/brand-link";
import { LinkButton } from "@/components/link-button";

/** Everything except the landing page needs a real desktop: the coding sandbox is an
 *  editor beside a terminal, and the mastery views are wide tables. Width alone can't
 *  express that -- an iPad Pro in landscape reports 1366px, wider than plenty of
 *  laptops -- so the pointer test is what actually excludes tablets. 1100px is where
 *  the 1040px reading column plus gutters stops fitting. */
const SUPPORTED = "@media (min-width:1100px) and (pointer:fine)";

/** Media queries rather than a `useMediaQuery` gate: this resolves before first paint,
 *  so small screens never flash the real app, and there is no SSR/client mismatch to
 *  reconcile. The URL is left untouched on purpose -- someone who opens a course link
 *  on a phone can reopen that same link on a laptop and land where they meant to. */
export function DesktopOnly({ children }: { children: React.ReactNode }) {
  return (
    <>
      {/* `contents` rather than `block` so the wrapper leaves no box behind on desktop:
          AppShell's sticky header and full-bleed height math both assume they sit
          directly in the document flow. */}
      <Box sx={{ display: "none", [SUPPORTED]: { display: "contents" } }}>{children}</Box>

      <Box
        sx={{
          display: "flex",
          [SUPPORTED]: { display: "none" },
          minHeight: "100dvh",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          px: { xs: 2, sm: 3 },
          py: 6
        }}
      >
        <Box sx={{ width: "100%", maxWidth: 480 }}>
          <BrandLink size="large" />
          <Typography variant="overline" color="text.secondary" sx={{ display: "block", mt: 6 }}>
            Desktop required
          </Typography>
          <Typography
            variant="h3"
            sx={{ fontSize: "clamp(1.75rem, 5vw, 2.5rem)", letterSpacing: "-0.02em", lineHeight: 1.15, my: "12px" }}
          >
            Canopy needs a bigger screen.
          </Typography>
          <Typography color="text.secondary" sx={{ fontSize: "1.05rem" }}>
            Lessons run beside a live code editor and terminal, so Canopy is built for a laptop or desktop
            display. Open this page on a computer to pick up where you left off.
          </Typography>
          <LinkButton href="/" variant="contained" size="large" sx={{ mt: 3 }}>
            Back to home
          </LinkButton>
        </Box>
      </Box>
    </>
  );
}
