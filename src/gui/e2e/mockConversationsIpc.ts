import type { Page } from "@playwright/test";

/** 内存档 B 存储，供 Playwright 在无 Electron 时演练 /cache（F6-04） */
export async function installMockConversationsIpc(
  page: Page,
  seed: Record<string, Record<string, unknown>>,
): Promise<void> {
  await page.addInitScript((initial) => {
    const store = new Map<string, Record<string, unknown>>(
      Object.entries(initial as Record<string, Record<string, unknown>>),
    );
    const metaFrom = (id: string, rec: Record<string, unknown>) => ({
      id,
      title: String(rec.title ?? id),
      status: String(rec.status ?? "idle"),
      updated_at: String(rec.updated_at ?? new Date(0).toISOString()),
      byte_size: JSON.stringify(rec).length,
    });
    window.logosElectron = {
      getDebugInfo: async () => ({ repo_root: "G:\\mock-repo" }),
      conversations: {
        root: async () => "G:\\mock-repo\\workspace\\conversations",
        list: async () =>
          Array.from(store.entries()).map(([id, rec]) => metaFrom(id, rec)),
        read: async (id: string) => {
          const rec = store.get(id);
          if (!rec) {
            return { ok: false, error: "not_found", corrupt: false };
          }
          return { ok: true, record: rec };
        },
        write: async (id: string, rec: Record<string, unknown>) => {
          store.set(id, { ...rec, id });
          return { ok: true };
        },
        delete: async (id: string) => {
          store.delete(id);
          return { ok: true };
        },
        totalBytes: async () => {
          let total = 0;
          for (const rec of store.values()) {
            total += JSON.stringify(rec).length;
          }
          return total;
        },
      },
    };
  }, seed);
}
