import { existsSync, readFileSync } from "fs";
import * as path from "path";
import { parse as parseYaml } from "yaml";

const DEFAULT_CONVERSATIONS_CACHE = "./workspace/conversations";

function deepMerge(
  base: Record<string, unknown>,
  override: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...base };
  for (const [key, val] of Object.entries(override)) {
    const prev = out[key];
    if (
      prev !== null &&
      typeof prev === "object" &&
      !Array.isArray(prev) &&
      val !== null &&
      typeof val === "object" &&
      !Array.isArray(val)
    ) {
      out[key] = deepMerge(
        prev as Record<string, unknown>,
        val as Record<string, unknown>,
      );
    } else {
      out[key] = val;
    }
  }
  return out;
}

function loadYamlDict(filePath: string): Record<string, unknown> {
  if (!existsSync(filePath)) {
    return {};
  }
  const raw = readFileSync(filePath, "utf8");
  const data = parseYaml(raw);
  if (data === null || data === undefined) {
    return {};
  }
  if (typeof data !== "object" || Array.isArray(data)) {
    return {};
  }
  return data as Record<string, unknown>;
}

function applyEnvOverrides(tree: Record<string, unknown>): void {
  const env = process.env;
  for (const [rawName, rawVal] of Object.entries(env)) {
    if (!rawName.startsWith("LOGOS_") || rawVal === "") {
      continue;
    }
    if (rawName === "LOGOS_CONFIG_DIR") {
      continue;
    }
    const body = rawName.slice("LOGOS_".length);
    const segments = body.split("__").filter(Boolean).map((s) => s.toLowerCase());
    if (!segments.length) {
      continue;
    }
    let node: Record<string, unknown> = tree;
    for (let i = 0; i < segments.length - 1; i += 1) {
      const seg = segments[i];
      const child = node[seg];
      if (typeof child !== "object" || child === null || Array.isArray(child)) {
        node[seg] = {};
      }
      node = node[seg] as Record<string, unknown>;
    }
    node[segments[segments.length - 1]] = rawVal;
  }
  const direct = env.LOGOS_CONVERSATIONS_CACHE?.trim();
  if (direct) {
    if (typeof tree.paths !== "object" || tree.paths === null || Array.isArray(tree.paths)) {
      tree.paths = {};
    }
    (tree.paths as Record<string, unknown>).CONVERSATIONS_CACHE = direct;
  }
}

export function resolveConfigDir(repoRoot: string): string {
  const fromEnv = process.env.LOGOS_CONFIG_DIR?.trim();
  if (fromEnv) {
    return path.resolve(fromEnv);
  }
  const candidate = path.join(repoRoot, "config");
  if (existsSync(path.join(candidate, "defaults.yaml"))) {
    return candidate;
  }
  return candidate;
}

export function loadMergedConfigDict(repoRoot: string): Record<string, unknown> {
  const dir = resolveConfigDir(repoRoot);
  const merged = deepMerge(
    loadYamlDict(path.join(dir, "defaults.yaml")),
    loadYamlDict(path.join(dir, "local.yaml")),
  );
  applyEnvOverrides(merged);
  return merged;
}

export function readConversationsCacheSetting(repoRoot: string): string {
  const explicit = process.env.LOGOS_CONVERSATIONS_CACHE?.trim();
  if (explicit) {
    return explicit;
  }
  const merged = loadMergedConfigDict(repoRoot);
  const paths = merged.paths;
  if (typeof paths !== "object" || paths === null || Array.isArray(paths)) {
    return DEFAULT_CONVERSATIONS_CACHE;
  }
  const p = paths as Record<string, unknown>;
  const raw = p.CONVERSATIONS_CACHE ?? p.conversations_cache;
  if (typeof raw === "string" && raw.trim()) {
    return raw.trim();
  }
  return DEFAULT_CONVERSATIONS_CACHE;
}

export function resolveConversationsCacheAbs(
  repoRoot: string,
  raw: string,
): string {
  const trimmed = raw.trim();
  if (path.isAbsolute(trimmed)) {
    return path.resolve(trimmed);
  }
  return path.resolve(repoRoot, trimmed);
}
