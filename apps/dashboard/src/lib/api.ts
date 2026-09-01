/**
 * Minimal typed client for the deRek AI OS API.
 *
 * Deliberately dependency-free: a thin `fetch` wrapper is preferable
 * to pulling in a full HTTP client library for this dashboard's needs
 * (health, version, and Task Engine endpoints).
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

// --- Task Engine types --------------------------------------------------------
//
// Mirrors packages/tasks/models.py exactly: the seven Task Lifecycle
// states and five Execution Modes from docs/PROJECT_BIBLE.md.

export type TaskState =
  | "Queued"
  | "Planning"
  | "Running"
  | "Waiting"
  | "Completed"
  | "Failed"
  | "Cancelled";

export type ExecutionMode =
  | "Interactive"
  | "Background"
  | "Scheduled"
  | "Event Driven"
  | "Autonomous";

export interface TaskTransition {
  from_state: TaskState | null;
  to_state: TaskState;
  reason: string | null;
  timestamp: string;
}

export interface TaskData {
  id: string;
  name: string;
  capability: string;
  execution_mode: ExecutionMode;
  input: Record<string, unknown>;
  state: TaskState;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  history: TaskTransition[];
}

export interface CreateTaskInput {
  name: string;
  capability: string;
  execution_mode?: ExecutionMode;
  input?: Record<string, unknown>;
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

async function postJson<T>(path: string, payload: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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

export function listTasks(signal?: AbortSignal): Promise<TaskData[]> {
  return request<TaskData[]>("/tasks", signal);
}

export function createTask(payload: CreateTaskInput, signal?: AbortSignal): Promise<TaskData> {
  return postJson<TaskData>("/tasks", payload, signal);
}
