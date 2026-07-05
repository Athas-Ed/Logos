import { useEffect, useState } from "react";

export type LookupEntry = { name: string; path: string; type: string };

export function useOutlineLookup(skillId?: string): {
  roles: { name: string; path: string }[];
  locations: { name: string; path: string }[];
} {
  const [roles, setRoles] = useState<{ name: string; path: string }[]>([]);
  const [locations, setLocations] = useState<{ name: string; path: string }[]>([]);

  useEffect(() => {
    if (skillId !== "outline_plan") return;
    const ac = new AbortController();
    fetch("/api/v1/ksfs/lookup", { signal: ac.signal })
      .then((r) => (r.ok ? (r.json() as Promise<LookupEntry[]>) : []))
      .then((data) => {
        setRoles(data.filter((d) => d.type === "role"));
        setLocations(data.filter((d) => d.type === "location"));
      })
      .catch(() => {});
    return () => ac.abort();
  }, [skillId]);

  return { roles, locations };
}
