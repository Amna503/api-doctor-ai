import type { Consumer } from "../types";

const METHODS = ["get", "put", "post", "delete", "options", "head", "patch", "trace"] as const;

export interface SpecInspection {
  valid: boolean;
  empty: boolean;
  error: string | null;
  title: string | null;
  version: string | null;
  openapi: string | null;
  operations: string[];
  endpointCount: number;
  bytes: number;
  lines: number;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

export function inspectSpec(text: string): SpecInspection {
  const bytes = new Blob([text]).size;
  const lines = text ? text.split("\n").length : 0;
  if (!text.trim()) {
    return {
      valid: false,
      empty: true,
      error: null,
      title: null,
      version: null,
      openapi: null,
      operations: [],
      endpointCount: 0,
      bytes,
      lines,
    };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (error) {
    return {
      valid: false,
      empty: false,
      error: error instanceof Error ? `Invalid JSON: ${error.message}` : "Invalid JSON",
      title: null,
      version: null,
      openapi: null,
      operations: [],
      endpointCount: 0,
      bytes,
      lines,
    };
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return {
      valid: false,
      empty: false,
      error: "The document must be a JSON object.",
      title: null,
      version: null,
      openapi: null,
      operations: [],
      endpointCount: 0,
      bytes,
      lines,
    };
  }
  const document = parsed as Record<string, unknown>;
  if (typeof document.openapi !== "string" && typeof document.swagger !== "string") {
    return {
      valid: false,
      empty: false,
      error: "Missing an `openapi` or `swagger` version field.",
      title: typeof document.info === "object" ? null : null,
      version: null,
      openapi: null,
      operations: [],
      endpointCount: 0,
      bytes,
      lines,
    };
  }
  if (!document.paths || typeof document.paths !== "object" || Array.isArray(document.paths)) {
    return {
      valid: false,
      empty: false,
      error: "Missing a `paths` object.",
      title: null,
      version: null,
      openapi: typeof document.openapi === "string" ? document.openapi : String(document.swagger),
      operations: [],
      endpointCount: 0,
      bytes,
      lines,
    };
  }
  const paths = document.paths as Record<string, unknown>;
  const operations: string[] = [];
  for (const [path, item] of Object.entries(paths)) {
    if (!item || typeof item !== "object") continue;
    for (const method of METHODS) {
      if (method in (item as Record<string, unknown>)) {
        operations.push(`${method.toUpperCase()} ${path}`);
      }
    }
  }
  const info =
    document.info && typeof document.info === "object" && !Array.isArray(document.info)
      ? (document.info as Record<string, unknown>)
      : null;
  return {
    valid: true,
    empty: false,
    error: null,
    title: info && typeof info.title === "string" ? info.title : null,
    version: info && typeof info.version === "string" ? info.version : null,
    openapi: typeof document.openapi === "string" ? document.openapi : String(document.swagger),
    operations,
    endpointCount: operations.length,
    bytes,
    lines,
  };
}

export function parseSpecDocument(text: string): Record<string, unknown> {
  const value = JSON.parse(text) as unknown;
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Spec must be a JSON object.");
  }
  return value as Record<string, unknown>;
}

export function parseConsumers(text: string): { consumers: Consumer[]; error: string | null } {
  if (!text.trim()) return { consumers: [], error: null };
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (error) {
    return {
      consumers: [],
      error: error instanceof Error ? `Invalid JSON: ${error.message}` : "Invalid consumer JSON",
    };
  }
  if (!Array.isArray(parsed)) {
    return { consumers: [], error: "Consumers must be a JSON array." };
  }
  const consumers: Consumer[] = [];
  for (let index = 0; index < parsed.length; index += 1) {
    const entry = parsed[index];
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
      return { consumers: [], error: `Consumer ${index + 1} must be an object.` };
    }
    const record = entry as Record<string, unknown>;
    if (typeof record.name !== "string" || !record.name.trim()) {
      return { consumers: [], error: `Consumer ${index + 1} needs a non-empty "name".` };
    }
    if (
      !Array.isArray(record.endpoints) ||
      record.endpoints.some((endpoint) => typeof endpoint !== "string")
    ) {
      return {
        consumers: [],
        error: `Consumer "${record.name}" needs an "endpoints" array of strings.`,
      };
    }
    consumers.push({
      name: record.name.trim(),
      owner: typeof record.owner === "string" ? record.owner : null,
      endpoints: record.endpoints as string[],
    });
  }
  return { consumers, error: null };
}
