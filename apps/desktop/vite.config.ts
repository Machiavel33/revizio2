import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Tauri attend un port fixe et ne doit pas effacer l'écran
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
  envPrefix: ["VITE_", "TAURI_"],
  build: {
    target: "es2021",
    minify: "esbuild",
    sourcemap: false,
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          pdf: ["jspdf"],
          motion: ["framer-motion"],
        },
      },
    },
  },
});
