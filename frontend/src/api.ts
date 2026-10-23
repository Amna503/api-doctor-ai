import type { AnalysisResult, AnalyzePayload, Health, VerificationResult, VerifyPayload } from "./types";

const configuredBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)
  ?.trim()
  .replace(/\/+$/, "");

export const API_BASE_URL =
  configuredBase || (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

export const REPOSITORY_URL =
  (import.meta.env.VITE_REPOSITORY_URL as string | undefined)?.trim() ||
  "https://github.com/Amna503/api-doctor-ai";

export class ApiError extends Error {
  status: number;
  detail: string;
  errors: unknown[];
  code?: string;

  constructor(message: string, status = 0, detail = "", errors: unknown[] = [], code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.errors = errors;
    this.code = code;
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 30000): Promise<T> {
  if (!API_BASE_URL) {
    throw new ApiError(
      "Backend URL is not configured. Set VITE_API_BASE_URL in the frontend deployment.",
      0,
      "Missing VITE_API_BASE_URL",
    );
  }
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(init.headers ?? {}),
      },
    });
    const text = await response.text();
    let body: unknown = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = null;
    }
    if (!response.ok) {
      const record = (body ?? {}) as Record<string, unknown>;
      const detail =
        typeof record.detail === "string"
          ? record.detail
          : `Request failed with HTTP ${response.status}`;
      throw new ApiError(
        detail,
        response.status,
        detail,
        Array.isArray(record.errors) ? record.errors : [],
        typeof record.code === "string" ? record.code : undefined,
      );
    }
    return body as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The diagnostic request timed out. The backend may be cold-starting.", 0);
    }
    throw new ApiError(
      error instanceof TypeError
        ? "Cannot reach the API Doctor backend. Check the deployment URL and CORS configuration."
        : "Unexpected network error.",
      0,
      String(error),
    );
  } finally {
    window.clearTimeout(timer);
  }
}

export function checkHealth(): Promise<Health> {
  return request<Health>("/health", {}, 15000);
}

export function analyzeSpecs(payload: AnalyzePayload): Promise<AnalysisResult> {
  return request<AnalysisResult>(
    "/api/analyze",
    { method: "POST", body: JSON.stringify(payload) },
    90000,
  );
}

export function verifySpecs(payload: VerifyPayload): Promise<VerificationResult> {
  return request<VerificationResult>(
    "/api/verify",
    { method: "POST", body: JSON.stringify(payload) },
    90000,
  );
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.errors.length > 0) {
      const first = error.errors[0] as Record<string, unknown> | string;
      if (typeof first === "string") return `${error.message} ${first}`;
      if (first && typeof first.msg === "string") return `${error.message} ${first.msg}`;
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Unknown error";
}
