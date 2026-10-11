import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": new URL("./src", import.meta.url).pathname,
    },
  },
  test: {
    clearMocks: true,
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    // Bound jsdom concurrency so large accessibility queries do not starve timers.
    maxWorkers: 2,
    restoreMocks: true,
  },
});
