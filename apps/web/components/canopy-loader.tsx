import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Traced from public/canopy-logo.svg. Inlined rather than <img> so the mark can be drawn
// twice -- a faint ghost underneath, and a full-colour copy clipped to the fill line.
const LOGO_PATHS = [
  { d: "m168.05156 212.3333c0 -117.26701 95.056656 -212.3307 212.31496 -212.3307c56.309418 0 110.31256 22.370493 150.12933 62.190224c39.816772 39.819736 62.185608 93.82689 62.185608 150.14049c0 117.26701 -95.05661 212.3307 -212.31494 212.3307c-117.2583 0 -212.31496 -95.06369 -212.31496 -212.3307z", fill: "#6aa84f" },
  { d: "m342.32758 719.9977l69.68506 -442.86615l69.68503 442.86615z", fill: "#964b00" },
  { d: "m387.61868 549.7398l-164.83466 -355.1181l225.1496 320.28345z", fill: "#964b00" },
  { d: "m400.38727 366.85754l145.07086 -113.44881l-113.44879 145.07088z", fill: "#964b00" },
  { d: "m460.29755 254.90858c0 -43.904465 35.591614 -79.49606 79.49609 -79.49606c21.083618 0 41.303772 8.375458 56.21216 23.28386c14.908447 14.9084015 23.283875 35.12854 23.283875 56.212204c0 43.904465 -35.591614 79.49608 -79.49603 79.49608c-43.90448 0 -79.49609 -35.591614 -79.49609 -79.49608z", fill: "#38761d" },
  { d: "m100.71001 191.34538c0 -79.01586 64.05501 -143.07086 143.07086 -143.07086c37.944748 0 74.3354 15.073494 101.1664 41.904488c26.830994 26.830994 41.90448 63.221634 41.90448 101.16638c0 79.015854 -64.05502 143.07088 -143.07088 143.07088c-79.015854 0 -143.07086 -64.05502 -143.07086 -143.07088z", fill: "#274e13" },
];

function CanopyMark() {
  return (
    <Box component="svg" viewBox="0 0 720 720" aria-hidden="true" focusable="false" sx={{ width: "100%", height: "100%", display: "block" }}>
      {LOGO_PATHS.map((path) => (
        <path key={path.d} d={path.d} fill={path.fill} fillRule="evenodd" />
      ))}
    </Box>
  );
}

/**
 * The logo filling from the ground up, so the trunk draws in before the canopy and the mark
 * reads as a tree growing rather than a generic spinner.
 *
 * `inset(100% 0 0 0)` clips the whole mark away; animating that top inset down to 0 uncovers
 * it from the bottom edge upward. Exported on its own for surfaces that supply their own
 * copy alongside it, such as the course build card.
 */
export function CanopyGrowMark({ size = 76 }: { size?: number }) {
  return (
    <Box aria-hidden="true" sx={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <Box sx={{ position: "absolute", inset: 0, opacity: 0.16 }}>
        <CanopyMark />
      </Box>
      <Box
        sx={{
          position: "absolute",
          inset: 0,
          animation: "canopy-grow 2s ease-in-out infinite",
          "@keyframes canopy-grow": {
            "0%": { clipPath: "inset(100% 0 0 0)", opacity: 1 },
            "55%": { clipPath: "inset(0% 0 0 0)", opacity: 1 },
            "78%": { clipPath: "inset(0% 0 0 0)", opacity: 1 },
            "96%": { clipPath: "inset(0% 0 0 0)", opacity: 0 },
            "100%": { clipPath: "inset(100% 0 0 0)", opacity: 0 },
          },
          // Motion is the whole point here, so with it suppressed just show the finished
          // mark rather than a frozen half-drawn tree.
          "@media (prefers-reduced-motion: reduce)": {
            animation: "none",
            clipPath: "none",
            opacity: 1,
          },
        }}
      >
        <CanopyMark />
      </Box>
    </Box>
  );
}

/** Branded waiting state: the growing mark plus a line of copy saying what is loading. */
export function CanopyLoader({ label = "Loading content…", size = 76, py = 8 }: { label?: string; size?: number; py?: number }) {
  return (
    <Stack role="status" aria-live="polite" sx={{ alignItems: "center", justifyContent: "center", gap: size > 56 ? 2 : 1.25, py }}>
      <CanopyGrowMark size={size} />
      <Typography variant="body2" color="text.secondary">{label}</Typography>
    </Stack>
  );
}
