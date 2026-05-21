import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { initApiBase } from "./api/apiBase";
import { App } from "./App";
import { applyGuiTheme, readThemeChoice } from "./theme";
import "./index.css";

async function boot(): Promise<void> {
  applyGuiTheme(readThemeChoice());
  await initApiBase();
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void boot();
