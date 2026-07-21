import { createHash } from "node:crypto";

export type CanonicalJsonValue =
  | null
  | boolean
  | number
  | string
  | CanonicalJsonValue[]
  | { [key: string]: CanonicalJsonValue };

export function canonicalStructureJson(value: CanonicalJsonValue): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return "[" + value.map(canonicalStructureJson).join(",") + "]";
  }
  const entries = Object.keys(value).sort().map((key) =>
    JSON.stringify(key) + ":" + canonicalStructureJson(value[key]!)
  );
  return "{" + entries.join(",") + "}";
}

export function structuralFingerprint(value: CanonicalJsonValue): string {
  return createHash("sha256")
    .update(canonicalStructureJson(value), "utf8")
    .digest("hex");
}
