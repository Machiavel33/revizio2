import preset from "@revizio/design-tokens/tailwind";

/** @type {import('tailwindcss').Config} */
export default {
  presets: [preset],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
};
