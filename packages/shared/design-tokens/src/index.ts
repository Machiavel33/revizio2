/**
 * Revizio — Design Tokens "DarkPunk Pro"
 * Source unique de vérité pour la palette, typo, ombres et rayons.
 * Consommé par le desktop (Tauri) et le web (React) via Tailwind preset + CSS vars.
 */

export const colors = {
  bg: {
    base: "#0A0B0F",
    surface: "#12141C",
    elevated: "#1A1D28",
    inset: "#07080B",
  },
  accent: {
    primary: "#00E5FF",
    secondary: "#B14EFF",
    success: "#00FFA3",
    warning: "#FFB800",
    danger: "#FF3B5C",
  },
  text: {
    primary: "#F0F2F8",
    secondary: "#A0A6B8",
    muted: "#5C6274",
    onAccent: "#0A0B0F",
  },
  border: {
    subtle: "#1F2330",
    strong: "#2E3444",
    glow: "rgba(0,229,255,0.35)",
  },
} as const;

export const gradients = {
  primary: "linear-gradient(135deg, #00E5FF 0%, #B14EFF 100%)",
  ambient:
    "radial-gradient(circle at 30% 0%, rgba(0,229,255,0.08) 0%, transparent 50%), radial-gradient(circle at 80% 100%, rgba(177,78,255,0.08) 0%, transparent 50%)",
  rec: "linear-gradient(135deg, #FF3B5C 0%, #FFB800 100%)",
} as const;

export const fonts = {
  display: ["Space Grotesk", "system-ui", "sans-serif"],
  sans: ["Inter", "system-ui", "sans-serif"],
  mono: ["JetBrains Mono", "monospace"],
} as const;

export const shadows = {
  card: "0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.03)",
  elevated: "0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,229,255,0.15)",
  glowCyan: "0 0 20px rgba(0,229,255,0.4), 0 0 40px rgba(0,229,255,0.15)",
  glowViolet: "0 0 20px rgba(177,78,255,0.4), 0 0 40px rgba(177,78,255,0.15)",
} as const;

export const radii = {
  sm: "6px",
  md: "12px",
  lg: "20px",
  full: "9999px",
} as const;

export const glass = {
  bg: "rgba(18,20,28,0.7)",
  blur: "blur(16px) saturate(140%)",
  border: "1px solid rgba(255,255,255,0.06)",
} as const;

export const tokens = {
  colors,
  gradients,
  fonts,
  shadows,
  radii,
  glass,
} as const;

export type Tokens = typeof tokens;
