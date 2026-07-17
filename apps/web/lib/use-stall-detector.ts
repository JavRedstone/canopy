import { useEffect, useRef, useState } from "react";

// Flags `stalled` once `signature` (progress counts/status) has stayed unchanged for `thresholdMs`; pass `null` when nothing is in-flight.
export function useStallDetector(signature: string | null, thresholdMs: number): boolean {
  const trackedRef = useRef<{ signature: string; since: number } | null>(null);
  const [stalled, setStalled] = useState(false);

  // Reacts to an external clock (elapsed wall time since the last observed signature change), not to renderable
  // React state, so there is no synchronous alternative to setState-in-effect here.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (signature === null) {
      trackedRef.current = null;
      setStalled(false);
      return;
    }
    if (!trackedRef.current || trackedRef.current.signature !== signature) {
      trackedRef.current = { signature, since: Date.now() };
      setStalled(false);
    }
    const elapsed = Date.now() - trackedRef.current.since;
    if (elapsed >= thresholdMs) {
      setStalled(true);
      return;
    }
    const timer = window.setTimeout(() => setStalled(true), thresholdMs - elapsed);
    return () => window.clearTimeout(timer);
  }, [signature, thresholdMs]);
  /* eslint-enable react-hooks/set-state-in-effect */

  return stalled;
}
