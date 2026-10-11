import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const backendUrl = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": backendUrl,
      "/healthz": backendUrl,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
