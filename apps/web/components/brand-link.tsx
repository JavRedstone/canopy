"use client";

import Link from "next/link";
import Typography from "@mui/material/Typography";

/** Same server/client boundary constraint as LinkButton -- see its comment. */
export function BrandLink() {
  return (
    <Typography
      component={Link}
      href="/"
      sx={{ fontWeight: 700, fontSize: "1.05rem", letterSpacing: "-0.01em", color: "inherit", textDecoration: "none" }}
    >
      Canopy
    </Typography>
  );
}
