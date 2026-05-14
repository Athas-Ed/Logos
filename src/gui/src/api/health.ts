import { apiUrl } from "./apiBase";

const HEALTH_PATH = "/api/v1/health";

export async function fetchHealth(): Promise<boolean> {
  try {
    const res = await fetch(apiUrl(HEALTH_PATH), { method: "GET" });
    if (!res.ok) return false;
    const data = (await res.json()) as { status?: string };
    return data.status === "ok";
  } catch {
    return false;
  }
}
