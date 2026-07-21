"use client";

import NextLink from "next/link";
import Box from "@mui/material/Box";
import Link from "@mui/material/Link";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { BrandLink } from "@/components/brand-link";

const REPO_URL = "https://github.com/JavRedstone/canopy";

// Only routes that actually exist -- a footer of dead links reads worse than no footer.
const PRODUCT_LINKS = [
  { label: "My courses", href: "/courses" },
  { label: "New course", href: "/courses/new" },
  { label: "Sandbox playground", href: "/courses/playground" },
];

/** Same client-file constraint as LinkButton -- see its comment. */
export function SiteFooter() {
  return (
    <Box component="footer" sx={{ borderTop: 1, borderColor: "divider", pt: 5, pb: 6 }}>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "1.6fr 1fr 1fr" },
          gap: { xs: 4, sm: 3 }
        }}
      >
        <Box>
          <BrandLink />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5, maxWidth: 320 }}>
            Source-grounded technical courses generated from your own documents.
          </Typography>
        </Box>

        <Stack sx={{ gap: 1 }}>
          <Typography variant="overline" color="text.secondary">Product</Typography>
          {PRODUCT_LINKS.map((link) => (
            <Link
              key={link.href}
              component={NextLink}
              href={link.href}
              variant="body2"
              underline="hover"
              color="text.primary"
            >
              {link.label}
            </Link>
          ))}
        </Stack>

        <Stack sx={{ gap: 1 }}>
          <Typography variant="overline" color="text.secondary">Project</Typography>
          <Link
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            variant="body2"
            underline="hover"
            color="text.primary"
          >
            Source on GitHub
          </Link>
        </Stack>
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mt: 5 }}>
        © {new Date().getFullYear()} Canopy
      </Typography>
    </Box>
  );
}
