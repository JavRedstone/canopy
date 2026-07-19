"use client";

import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Link from "@mui/material/Link";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { CertificateResponse } from "@/lib/api";

function formatHours(hours: number): string {
  const text = Number.isInteger(hours) ? String(hours) : hours.toFixed(1);
  return `~${text} hour${hours === 1 ? "" : "s"}`;
}

/** The certificate itself -- shared by the in-app dialog and the public verification
 *  page so the two never drift apart, and matching certificate_pdf.py's layout/theming
 *  (small de-emphasized brand mark, course-themed accent color, wrapping skill chips,
 *  verification as just the link) so the PDF and the site show the same thing. */
export function CertificateCard({ certificate }: { certificate: CertificateResponse }) {
  const { accent_color: accent, accent_tint: tint } = certificate;
  return (
    <Box
      sx={{
        position: "relative", p: { xs: 3, sm: 5 }, borderRadius: 3, textAlign: "center",
        bgcolor: "background.paper", border: `2px solid ${accent}`, boxShadow: `0 18px 40px ${accent}26`
      }}
    >
      <Box sx={{ position: "absolute", inset: 8, border: `1px solid ${accent}55`, borderRadius: 2, pointerEvents: "none" }} />
      <Stack sx={{ alignItems: "center", gap: 1 }}>
        <Typography sx={{ fontWeight: 800, fontSize: "0.85rem", letterSpacing: "0.08em", color: "text.primary" }}>CANOPY</Typography>
        <Typography variant="overline" sx={{ letterSpacing: "0.13em", fontWeight: 700, color: accent, mb: 1 }}>Certificate of completion</Typography>
        <Typography color="text.secondary">This certifies that</Typography>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>{certificate.learner_name}</Typography>
        <Typography color="text.secondary">has successfully completed</Typography>
        <Typography variant="h4" sx={{ fontWeight: 800, color: accent, letterSpacing: "-0.02em", mb: 1 }}>{certificate.course_title}</Typography>
        {certificate.skills.length > 0 ? (
          <>
            <Typography variant="caption" sx={{ letterSpacing: "0.1em", color: "text.secondary" }}>SKILLS COVERED</Typography>
            <Stack direction="row" sx={{ flexWrap: "wrap", gap: 0.75, justifyContent: "center", mt: 0.75 }}>
              {certificate.skills.map((skill) => (
                <Chip key={skill} size="small" label={skill.toUpperCase()} sx={{ bgcolor: tint, color: accent, fontWeight: 700 }} />
              ))}
            </Stack>
          </>
        ) : null}
        <Typography sx={{ fontWeight: 700, mt: 1.5 }}>
          {formatHours(certificate.estimated_hours)} · Issued {new Date(certificate.issued_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}
        </Typography>
        <Link href={certificate.verify_url} target="_blank" rel="noopener noreferrer" sx={{ fontSize: "0.8rem", color: accent, mt: 1.5, wordBreak: "break-all" }}>
          Verify at {certificate.verify_url}
        </Link>
      </Stack>
    </Box>
  );
}
