import Box from "@mui/material/Box";

// Straight from public/canopy-logo.svg. Rendered at low opacity over the near-white
// background so they read as muted washes rather than flat brand color.
const CANOPY_GREEN = "#6aa84f";
const SHADOW_GREEN = "#274e13";
const MID_GREEN = "#38761d";
const TRUNK_BROWN = "#964b00";

/** Decorative background wash for the landing hero. Spans the full viewport rather than the
 *  reading column, so the shapes live mostly in the page margins and stay out of the way of
 *  the copy. aria-hidden and non-interactive; AppShell's overflowX:hidden clips the bleed. */
export function CanopyBlobs() {
  return (
    <Box
      sx={{
        position: "absolute",
        top: 0,
        bottom: 0,
        left: "50%",
        transform: "translateX(-50%)",
        width: "100vw",
        pointerEvents: "none",
        zIndex: 0,
        // Without this the layer's own box edge shows as a hard horizontal line where the
        // tint stops. Dissolving top and bottom keeps it reading as ambient background.
        maskImage: "linear-gradient(to bottom, transparent, #000 22%, #000 60%, transparent)",
        WebkitMaskImage: "linear-gradient(to bottom, transparent, #000 22%, #000 60%, transparent)"
      }}
    >
      <Box
        component="svg"
        aria-hidden="true"
        focusable="false"
        viewBox="0 0 1600 520"
        preserveAspectRatio="xMidYMid slice"
        sx={{ width: "100%", height: "100%", display: "block" }}
      >
        <circle cx="150" cy="150" r="210" fill={CANOPY_GREEN} opacity="0.13" />
        <circle cx="255" cy="365" r="95" fill={MID_GREEN} opacity="0.09" />
        <path
          d="M40 300c34-62 112-78 158-34s31 124-27 155-138 7-158-49c-13-38-4-45 27-72z"
          fill={TRUNK_BROWN}
          opacity="0.09"
        />
        <circle cx="1450" cy="170" r="215" fill={CANOPY_GREEN} opacity="0.13" />
        <circle cx="1305" cy="400" r="120" fill={SHADOW_GREEN} opacity="0.08" />
        <circle cx="1540" cy="415" r="55" fill={TRUNK_BROWN} opacity="0.11" />
      </Box>
    </Box>
  );
}
