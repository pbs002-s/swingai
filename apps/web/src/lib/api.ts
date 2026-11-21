/** Typed client for the StitchSense API (docs/API.md). Same-origin; cookies carry the session. */

import { MockError, mockApi } from "@/lib/demo-mock";

export type ApiError ={ code: string; message: string; details?: unknown };
type Envelope<T> = { success: boolean; data: T; error: ApiError | null; meta: Record<string, unknown> };

export class ApiFailure extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)ss_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

const DEMO = process.env.NEXT_PUBLIC_DEMO === "1";
const MOCK_FLAG = "ss_demo_mock";

/** True once a demo build has found no API and switched to built-in fixture data. */
export const isMockMode = () => DEMO && typeof sessionStorage !== "undefined" && sessionStorage.getItem(MOCK_FLAG) === "1";

function fromMock<T>(path: string, method: string, init: RequestInit): { data: T; meta: Record<string, unknown> } {
  sessionStorage.setItem(MOCK_FLAG, "1");
  try {
    const body = typeof init.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
    return mockApi(path, method, body) as { data: T; meta: Record<string, unknown> };
  } catch (e) {
    if (e instanceof MockError) throw new ApiFailure(e.status, e.code, e.message);
    throw e;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<{ data: T; meta: Record<string, unknown> }> {
  const method = (init.method ?? "GET").toUpperCase();
  if (isMockMode()) return fromMock<T>(path, method, init);
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) headers.set("content-type", "application/json");
  if (method !== "GET") headers.set("x-csrf-token", csrfToken());
  headers.set("accept-language", document.documentElement.lang === "bn" ? "bn" : "en"); // errors come back in the UI language
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { ...init, method, headers, credentials: "same-origin" });
  } catch {
    if (DEMO) return fromMock<T>(path, method, init);
    throw new ApiFailure(0, "NETWORK", "Cannot reach the server. Check the connection.");
  }
  let body: Envelope<T> | null = null;
  try {
    body = (await res.json()) as Envelope<T>;
  } catch {
    /* non-JSON response */
  }
  if (DEMO && (!body || typeof body.success !== "boolean")) return fromMock<T>(path, method, init); // no API behind this host
  if (!res.ok || !body?.success) {
    const err = body?.error;
    throw new ApiFailure(res.status, err?.code ?? "HTTP_ERROR", err?.message ?? "Something went wrong. Try again.");
  }
  return { data: body.data, meta: body.meta };
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const patch = <T>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body: JSON.stringify(body) });

// ---------- shapes ----------
export type Role = { role: string; scope_type: string; scope_id: number | null };
export type Me = { id: number; email: string; full_name: string; locale: string; roles: Role[] };
export type TileState = "running" | "idle" | "down" | "break" | "no_data";
export type Shift = { start: string; end: string; breaks: [string, string][] };

export type Overview = {
  as_of: string;
  factory: { id: number; name: string };
  shift: Shift;
  totals: {
    stations: number;
    states: Partial<Record<TileState, number>>;
    output: number;
    target: number;
    efficiency_pct: number | null;
    target_efficiency_pct: number;
    open_alerts: { critical: number; warning: number; info: number };
  };
  lines: {
    id: number;
    code: string;
    name: string;
    operation: string | null;
    states: Partial<Record<TileState, number>>;
    output: number;
    target: number;
    efficiency_pct: number | null;
    open_alerts: { critical: number; warning: number; info: number };
  }[];
  hourly: { hour: string; output: number; is_break: boolean }[];
  devices: { kind: string; total: number; online: number }[];
};

export type FloorStation = {
  id: number;
  code: string;
  position: number;
  state: TileState;
  worker_state: string | null;
  since: string | null;
  worker: { id: number; name: string; name_bn: string | null } | null;
  operation: { id: number; name: string; smv: number } | null;
  output: number;
  target: number;
  pending_reviews: number;
};
export type Floor = { line: { id: number; code: string; name: string }; shift: Shift; as_of: string; stations: FloorStation[] };

export type Segment = { state: string; start: string; end: string | null; event_id: number; review_status: string };
export type Timeline = {
  station: { id: number; code: string; line: string | null };
  worker: { id: number; name: string } | null;
  operation: { name: string; smv: number } | null;
  shift: Shift;
  lanes: { worker_state: Segment[]; machine_state: Segment[] };
  minutes: Record<string, number>;
  output: number;
  efficiency_pct: number | null;
};

export type ReviewItem = {
  id: number;
  event_type: string;
  state: string;
  title: string;
  station: { id: number; code: string };
  line: { id: number; name: string };
  worker: { id: number; name: string } | null;
  start_time: string;
  duration_s: number | null;
  confidence: number | null;
  source: string;
  model_version: string | null;
};

export type Alert = {
  id: number;
  type: string;
  severity: "critical" | "warning" | "info";
  title: string;
  detail: string;
  status: "open" | "acknowledged" | "resolved";
  confidence: number | null;
  event_id: number | null;
  station: { id: number; code: string } | null;
  line: { id: number; name: string } | null;
  created_at: string;
};

export type AlertRule = {
  id: number;
  name: string;
  kind: string;
  condition: Record<string, number | string>;
  severity: "critical" | "warning" | "info";
  recipient_roles: string[];
  is_enabled: boolean;
};

export type NeedleLot = {
  batch_id: number;
  lot_no: string;
  supplier: string;
  model: string;
  status: string;
  issued: number;
  confirmed_breaks: number;
  running_hours: number;
  break_rate_pct: number;
  breaks_per_1000h: number;
  machines: number;
  workers: number;
  pattern: "batch" | "machine" | "worker" | "normal" | "too_little_use";
};

export type OrgTree = {
  id: number;
  name: string;
  floors: { id: number; name: string; lines: { id: number; code: string; name: string; stations: number }[] }[];
}[];
