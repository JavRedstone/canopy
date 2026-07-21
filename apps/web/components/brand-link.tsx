"use client";

import Link from "next/link";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

const sizes = {
  default: { image: 26, font: "1.15rem", gap: 0.75 },
  large: { image: 44, font: "2rem", gap: 1.25 },
};

/** Same server/client boundary constraint as LinkButton -- see its comment. */
export function BrandLink({ size = "default" }: { size?: "default" | "large" }) {
  const { image, font, gap } = sizes[size];
  return (
    <Stack
      component={Link}
      href="/"
      direction="row"
      sx={{ alignItems: "center", gap, textDecoration: "none", color: "inherit" }}
    >
      {/* The mark is geometrically centred in its 720x720 viewBox, but its ink is not:
          the canopy circles carry nearly all the weight up top while the trunk tapers
          down to y720, putting the area-weighted centre around y263. Centring the box
          therefore reads as the tree floating high next to the wordmark, so nudge it
          back down. Percent rather than pixels so both size presets scale together. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/canopy-logo.svg" alt="" width={image} height={image} style={{ transform: "translateY(6%)" }} />
      <Typography sx={{ fontWeight: 700, fontSize: font, letterSpacing: "-0.01em", color: "inherit" }}>
        Canopy
      </Typography>
    </Stack>
  );
}
