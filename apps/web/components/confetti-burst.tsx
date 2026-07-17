"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import Box from "@mui/material/Box";

const CONFETTI_COLORS = ["#f5c518", "#34c759", "#0a84ff", "#ff453a", "#bf5af2"];

interface Piece {
  id: number;
  x: number;
  y: number;
  rotate: number;
  color: string;
  delay: number;
}

function makePieces(count: number): Piece[] {
  return Array.from({ length: count }, (_, index) => ({
    id: index,
    x: (Math.random() - 0.5) * 240,
    y: -(70 + Math.random() * 150),
    rotate: (Math.random() - 0.5) * 480,
    color: CONFETTI_COLORS[index % CONFETTI_COLORS.length],
    delay: Math.random() * 0.1
  }));
}

/** A brief, self-cleaning confetti burst for success moments (a correct quiz answer, all
 *  tests passing). Mount it with a fresh `key` each time the moment happens -- inside a
 *  `position: relative` (or already-positioned) container -- and it removes itself once
 *  its animation finishes. */
export function ConfettiBurst() {
  const [pieces] = useState(() => makePieces(28));
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(false), 900);
    return () => window.clearTimeout(timer);
  }, []);

  if (!visible) return null;

  return (
    <Box aria-hidden="true" sx={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden", zIndex: 2 }}>
      {pieces.map((piece) => (
        <motion.span
          key={piece.id}
          initial={{ opacity: 1, x: 0, y: 0, rotate: 0 }}
          animate={{ opacity: 0, x: piece.x, y: piece.y, rotate: piece.rotate }}
          transition={{ duration: 0.85, delay: piece.delay, ease: "easeOut" }}
          style={{
            position: "absolute",
            left: "50%",
            top: "50%",
            width: 7,
            height: 7,
            borderRadius: 2,
            backgroundColor: piece.color
          }}
        />
      ))}
    </Box>
  );
}
