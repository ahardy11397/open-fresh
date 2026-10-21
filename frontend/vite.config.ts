/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/settings": "http://localhost:4269",
      "/items": "http://localhost:4269",
      "/inventory": "http://localhost:4269",
      "/recipes": "http://localhost:4269",
      "/plan": "http://localhost:4269",
      "/list": "http://localhost:4269",
      "/prices": "http://localhost:4269",
      "/budget": "http://localhost:4269",
      "/spend": "http://localhost:4269",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
