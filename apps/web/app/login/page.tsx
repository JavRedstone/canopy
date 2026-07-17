import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { LoginForm } from "@/components/login-form";
import { PageShell } from "@/components/page-shell";
import { BrandLink } from "@/components/brand-link";

export default function LoginPage() {
  return (
    <PageShell>
      <BrandLink />
      <Box sx={{ maxWidth: 480, mt: 7 }}>
        <Typography variant="overline" color="text.secondary">Welcome</Typography>
        <Typography variant="h3" sx={{ fontSize: "clamp(2rem, 5vw, 3rem)", letterSpacing: "-0.02em", lineHeight: 1.1, my: "12px" }}>
          Start with your source material.
        </Typography>
        <Typography color="text.secondary" sx={{ fontSize: "1.05rem" }}>
          Use a passwordless sign-in link to keep your courses and documents private.
        </Typography>
        <LoginForm />
      </Box>
    </PageShell>
  );
}
