import { defineConfig } from "vite";

export default defineConfig({
  server: {
    proxy: {
      "/api": {
        target: process.env.TELEMETRY_BACKEND_ORIGIN || "http://localhost:5175",
        changeOrigin: true,
        headers: { origin: "http://localhost:5173" },
      },
    },
  },
});
