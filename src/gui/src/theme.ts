const THEME_KEY = "logos_gui_theme";

export type GuiThemeChoice = "system" | "light" | "dark";

export function readThemeChoice(): GuiThemeChoice {
  try {
    const raw = localStorage.getItem(THEME_KEY);
    if (raw === "light" || raw === "dark" || raw === "system") {
      return raw;
    }
  } catch {
    /* ignore */
  }
  return "system";
}

export function applyGuiTheme(choice: GuiThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", choice);
  }
  try {
    localStorage.setItem(THEME_KEY, choice);
  } catch {
    /* ignore */
  }
}
