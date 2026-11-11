/**
 * Revizio — Tailwind preset partagé (DarkPunk Pro).
 * Usage dans tailwind.config.js :
 *   import preset from "@revizio/design-tokens/tailwind";
 *   export default { presets: [preset], content: [...] };
 */
import { colors, fonts, shadows, radii } from "./index.ts";

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: colors.bg,
        accent: colors.accent,
        text: colors.text,
        border: colors.border,
      },
      fontFamily: {
        display: fonts.display,
        sans: fonts.sans,
        mono: fonts.mono,
      },
      boxShadow: {
        card: shadows.card,
        elevated: shadows.elevated,
        "glow-cyan": shadows.glowCyan,
        "glow-violet": shadows.glowViolet,
      },
      borderRadius: {
        sm: radii.sm,
        md: radii.md,
        lg: radii.lg,
      },
      backgroundImage: {
        "grad-primary": "linear-gradient(135deg, #00E5FF 0%, #B14EFF 100%)",
        "grad-rec": "linear-gradient(135deg, #FF3B5C 0%, #FFB800 100%)",
      },
    },
  },
};
