import Container from "@mui/material/Container";

/** The centered, max-width reading column every non-full-bleed page uses. Full-bleed
 *  views (the coding lab) render outside this, straight into AppShell's main area. */
export function PageShell({ children, maxWidth = 1040 }: { children: React.ReactNode; maxWidth?: number | { xs: number; xl: number } }) {
  return (
    <Container maxWidth={false} sx={{ maxWidth, pt: 3.5, pb: 8, px: { xs: 2, sm: 3 } }}>
      {children}
    </Container>
  );
}
