import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { DesktopOnly } from "@/components/desktop-only";
import { LoginForm } from "@/components/login-form";
import { BrandLink } from "@/components/brand-link";

// Deliberately not wrapped in PageShell: this is a single-task page, so it centers in the
// viewport rather than sitting at the top of the shared reading column.
export default function LoginPage() {
  return (
    <DesktopOnly>
      <Box
        sx={{
          minHeight: "100dvh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          px: { xs: 2, sm: 3 },
          py: 6,
        }}
      >
        <Box sx={{ width: "100%", maxWidth: 480 }}>
          <BrandLink size="large" />
          <Typography variant="overline" color="text.secondary" sx={{ display: "block", mt: 6 }}>
            Welcome
          </Typography>
          <Typography variant="h3" sx={{ fontSize: "clamp(2rem, 5vw, 3rem)", letterSpacing: "-0.02em", lineHeight: 1.1, my: "12px" }}>
            Start with your source material.
          </Typography>
          <Typography color="text.secondary" sx={{ fontSize: "1.05rem" }}>
            Use a passwordless sign-in link to keep your courses and documents private.
          </Typography>
          <LoginForm />
        </Box>
      </Box>
    </DesktopOnly>
  );
}
