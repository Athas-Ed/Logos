export type DeveloperUiState = {
  show_dev_tools_ui: boolean;
  prompt_echo: boolean;
};

export async function fetchDeveloperUi(): Promise<DeveloperUiState | null> {
  try {
    const r = await fetch("/api/v1/developer/ui");
    if (!r.ok) return null;
    return (await r.json()) as DeveloperUiState;
  } catch {
    return null;
  }
}

export async function putPromptEcho(enabled: boolean): Promise<boolean> {
  const r = await fetch("/api/v1/developer/prompt-echo", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  return r.ok;
}
