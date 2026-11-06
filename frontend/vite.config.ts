/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En desarrollo, las peticiones a /api se reenvían al backend FastAPI.
// Así el navegador habla con un solo origen y no depende de CORS.
const apiTarget = process.env.DERMAI_API_PROXY ?? "http://127.0.0.1:8000";

export default defineConfig({
  // Ruta pública de la aplicación: "/" en local; "/dermai/" en GitHub Pages.
  base: process.env.VITE_BASE_PATH ?? "/",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        // Si el backend no responde, Vite contestaría un 500 vacío. Devolvemos un 502
        // con el mismo formato de error que la API para que la interfaz lo explique bien.
        configure: (proxy) => {
          proxy.on("error", (_error, _request, response) => {
            if (!("writeHead" in response) || response.headersSent) return;
            response.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
            response.end(
              JSON.stringify({
                detail: `No se pudo conectar con el backend en ${apiTarget}. Comprueba que el servidor FastAPI está en marcha.`,
              }),
            );
          });
        },
      },
    },
  },
  // `npm run preview`: sirve el build de producción para probarlo en local.
  preview: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    mockReset: true,
    restoreMocks: true,
    unstubGlobals: true,
    coverage: {
      provider: "v8",
      include: ["src/**"],
      exclude: ["src/**/*.test.*", "src/test/**", "src/main.tsx", "src/vite-env.d.ts"],
      reporter: ["text-summary", "text"],
    },
  },
});
