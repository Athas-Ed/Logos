import { readFileSync } from "node:fs";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const guiVersion = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf8"),
) as { version?: string };

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target =
    env.VITE_DEV_API_PROXY_TARGET?.trim() || "http://127.0.0.1:8000";

  return {
    base: "./",
    define: {
      __LOGOS_GUI_VERSION__: JSON.stringify(guiVersion.version ?? "0.0.0"),
    },
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
        },
      },
    },
  };
});
