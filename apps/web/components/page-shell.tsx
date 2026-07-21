import Container from "@mui/material/Container";

/** Width and gutters of the reading column. AppShell's header imports both so the
 *  brand mark lines up with the content beneath it instead of hugging the viewport. */
export const CONTENT_MAX_WIDTH = 1040;
export const CONTENT_PX = { xs: 2, sm: 3 };

/** The centered, max-width reading column every non-full-bleed page uses. Full-bleed
 *  views (the coding lab) render outside this, straight into AppShell's main area. */
export function PageShell({ children, maxWidth = CONTENT_MAX_WIDTH }: { children: React.ReactNode; maxWidth?: number | { xs: number; xl: number } }) {
  return (
    <Container maxWidth={false} sx={{ maxWidth, pt: 3.5, pb: 8, px: CONTENT_PX }}>
      {children}
    </Container>
  );
}
