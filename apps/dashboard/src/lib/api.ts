/**
 * Minimal typed client for the deRek AI OS API.
 *
 * Deliberately dependency-free: the dashboard skeleton only needs to
 * call two read-only endpoints (health and version), so a thin fetch
 * wrapper is preferable to pulling in a full HTTP client library.
 *
 * Every backend response is wrapped in a `StandardResponse` envelope
 * (`success`, `message`, `data`, `request_id`, `timestamp`) — this
 * client unwraps `data` for callers.
 */

const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

interface StandardResponse<T> {
  success: boolean;
  message: string;
  data: T | null;
  request_id: string;
  timestamp: string;
}

export interface HealthData {
  status: string;
}

export interface VersionData {
  name: string;
  version: string;
  environment: string;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  const body = (await response.json()) as StandardResponse<T>;

  if (!response.ok || !body.success || body.data === null) {
    throw new ApiError(body.message || `Request to ${path} failed`, response.status);
  }

  return body.data;
}

export function getHealth(signal?: AbortSignal): Promise<HealthData> {
  return request<HealthData>("/health", signal);
}

export function getVersion(signal?: AbortSignal): Promise<VersionData> {
  return request<VersionData>("/version", signal);
}
