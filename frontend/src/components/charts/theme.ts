/* Categorical palette, fixed assignment order — validated for lightness band,
   chroma floor, CVD separation, and contrast on the light surface. */
export const SERIES_COLORS = ["#2489e9", "#7c3aed", "#0d9488", "#db2777"];

export const GRID_STROKE = "#e2e8ee";
export const AXIS_TICK = {
  fill: "#5b6b7b",
  fontSize: 10.5,
  fontFamily: "var(--font-jetbrains)",
} as const;

export const TOOLTIP_STYLE = {
  contentStyle: {
    fontSize: 12,
    fontFamily: "var(--font-plex)",
    border: "1px solid #e2e8ee",
    borderRadius: 6,
    boxShadow: "0 2px 8px rgba(16,21,29,0.08)",
  },
  labelStyle: { color: "#16202b", fontWeight: 600 },
} as const;
