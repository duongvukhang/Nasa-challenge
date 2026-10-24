/**
 * Deterministic color palette and color generator for multi-epoch source tracks.
 * Reused consistently across image overlay, sky plot, track list, and trajectory inspector.
 */

export const TRACK_PALETTE = [
  "#22d3ee",  // Cyan
  "#34d399",  // Emerald
  "#f59e0b",  // Amber
  "#c084fc",  // Purple
  "#fb7185",  // Rose
  "#38bdf8",  // Sky Blue
  "#e879f9",  // Fuchsia
  "#a3e635",  // Lime
];

export function getStableTrackColor(trackId) {
  if (!trackId) return TRACK_PALETTE[0];
  let h = 0;
  for (let i = 0; i < trackId.length; i++) {
    h = ((h * 31) + trackId.charCodeAt(i)) >>> 0;
  }
  return TRACK_PALETTE[h % TRACK_PALETTE.length];
}
