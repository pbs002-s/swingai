/** Offline demo data. Used when NEXT_PUBLIC_DEMO=1 and the real API cannot be reached (static/Vercel demo). */

const NOW = () => new Date();
const iso = (minAgo: number) => new Date(NOW().getTime() - minAgo * 60_000).toISOString();
const DEMO_PASSWORD = "stitchsense-demo";
const SESSION_KEY = "ss_demo_user";

const USERS: Record<string, { id: number; full_name: string; role: string }> = {
  "admin@stitchsense.local": { id: 1, full_name: "Demo Admin", role: "factory_admin" },
  "supervisor@stitchsense.local": { id: 2, full_name: "Demo Supervisor", role: "supervisor" },
  "quality@stitchsense.local": { id: 3, full_name: "Demo Quality", role: "quality" },
  "maintenance@stitchsense.local": { id: 4, full_name: "Demo Maintenance", role: "maintenance" },
  "manager@stitchsense.local": { id: 5, full_name: "Demo Manager", role: "management" },
};

class MockError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

function currentMe() {
  const email = typeof sessionStorage === "undefined" ? null : sessionStorage.getItem(SESSION_KEY);
  const u = email ? USERS[email] : undefined;
  if (!email || !u) throw new MockError(401, "UNAUTHENTICATED", "Please log in.");
  return { id: u.id, email, full_name: u.full_name, locale: "en", roles: [{ role: u.role, scope_type: "factory", scope_id: 1 }] };
}

const LINES = [
  { id: 1, code: "L1", name: "Line 1 · Shirts", stations: 12 },
  { id: 2, code: "L2", name: "Line 2 · Trousers", stations: 12 },
  { id: 3, code: "L3", name: "Line 3 · Polo", stations: 12 },
];
const OPS = [
  ["Collar attach", 1.2], ["Sleeve join", 0.9], ["Side seam", 0.7], ["Hem", 0.5], ["Placket", 1.1], ["Cuff attach", 0.8],
] as const;
const NAMES = ["Rahima Begum", "Shapla Akter", "Jorina Khatun", "Mina Das", "Sumi Rani", "Nasrin Sultana", "Fatema Khatun", "Rupa Akter", "Lipi Begum", "Asma Khatun", "Parul Islam", "Rokeya Khatun"];
const STATES = ["running", "running", "running", "running", "running", "idle", "running", "down", "running", "running", "break", "running"] as const;

const shift = { start: "08:00", end: "17:00", breaks: [["12:30", "13:30"]] as [string, string][] };

function floor(lineId: number) {
  const line = LINES.find((l) => l.id === lineId) ?? LINES[0];
  return {
    line: { id: line.id, code: line.code, name: line.name },
    shift,
    as_of: iso(0),
    stations: Array.from({ length: line.stations }, (_, i) => {
      const [opName, smv] = OPS[(i + lineId) % OPS.length];
      const target = 120;
      const output = STATES[i] === "down" ? 40 : 78 + ((i * 7 + lineId * 5) % 38);
      return {
        id: lineId * 100 + i + 1,
        code: `${line.code}-S${String(i + 1).padStart(2, "0")}`,
        position: i + 1,
        state: STATES[(i + lineId) % STATES.length],
        worker_state: "working",
        since: iso(5 + i * 3),
        worker: { id: i + 1, name: NAMES[i % NAMES.length], name_bn: null },
        operation: { id: (i % OPS.length) + 1, name: opName, smv },
        output,
        target,
        pending_reviews: i % 5 === 0 ? 1 : 0,
      };
    }),
  };
}

function overview() {
  const lines = LINES.map((l) => {
    const f = floor(l.id).stations;
    const states: Record<string, number> = {};
    f.forEach((s) => (states[s.state] = (states[s.state] ?? 0) + 1));
    const output = f.reduce((a, s) => a + s.output, 0);
    const target = f.reduce((a, s) => a + s.target, 0);
    return {
      id: l.id, code: l.code, name: l.name, operation: OPS[l.id][0], states, output, target,
      efficiency_pct: Math.round((output / target) * 1000) / 10,
      open_alerts: { critical: l.id === 2 ? 1 : 0, warning: 1, info: 0 },
    };
  });
  const states: Record<string, number> = {};
  lines.forEach((l) => Object.entries(l.states).forEach(([k, v]) => (states[k] = (states[k] ?? 0) + v)));
  const output = lines.reduce((a, l) => a + l.output, 0);
  const target = lines.reduce((a, l) => a + l.target, 0);
  return {
    as_of: iso(0),
    factory: { id: 1, name: "Demo Garments Ltd" },
    shift,
    totals: {
      stations: 36, states, output, target,
      efficiency_pct: Math.round((output / target) * 1000) / 10,
      target_efficiency_pct: 65,
      open_alerts: { critical: 1, warning: 3, info: 0 },
    },
    lines,
    hourly: ["08", "09", "10", "11", "12", "13", "14", "15", "16"].map((h) => ({
      hour: `${h}:00`, output: h === "12" ? 40 : 150 + ((Number(h) * 13) % 60), is_break: h === "12",
    })),
    devices: [
      { kind: "current_sensor", total: 36, online: 35 },
      { kind: "camera", total: 6, online: 6 },
    ],
  };
}

const ALERTS = [
  { id: 1, type: "machine_down", severity: "critical", title: "Machine down 14 min", detail: "L2-S08 current sensor shows no load.", status: "open", confidence: 0.94, event_id: null, station: { id: 208, code: "L2-S08" }, line: { id: 2, name: "Line 2 · Trousers" }, created_at: iso(14) },
  { id: 2, type: "needle_break", severity: "warning", title: "Needle break suspected", detail: "Check batch N-2291 before blaming the operator.", status: "open", confidence: 0.71, event_id: null, station: { id: 105, code: "L1-S05" }, line: { id: 1, name: "Line 1 · Shirts" }, created_at: iso(32) },
  { id: 3, type: "phone_use", severity: "warning", title: "Possible phone use", detail: "Needs supervisor review. Not confirmed.", status: "open", confidence: 0.58, event_id: null, station: { id: 304, code: "L3-S04" }, line: { id: 3, name: "Line 3 · Polo" }, created_at: iso(47) },
  { id: 4, type: "idle", severity: "warning", title: "Long idle time", detail: "6 min idle with machine on.", status: "acknowledged", confidence: 0.88, event_id: null, station: { id: 109, code: "L1-S09" }, line: { id: 1, name: "Line 1 · Shirts" }, created_at: iso(75) },
];

const NEEDLES = [
  { batch_id: 1, lot_no: "N-2291", supplier: "Groz-Beckert", model: "DBx1 90/14", status: "active", issued: 120, confirmed_breaks: 9, running_hours: 410, break_rate_pct: 7.5, breaks_per_1000h: 22, machines: 8, workers: 9, pattern: "batch" },
  { batch_id: 2, lot_no: "N-2304", supplier: "Organ", model: "DPx5 100/16", status: "active", issued: 90, confirmed_breaks: 2, running_hours: 380, break_rate_pct: 2.2, breaks_per_1000h: 5.3, machines: 7, workers: 8, pattern: "normal" },
  { batch_id: 3, lot_no: "N-2310", supplier: "Schmetz", model: "134 R 90", status: "active", issued: 60, confirmed_breaks: 4, running_hours: 150, break_rate_pct: 6.7, breaks_per_1000h: 26.7, machines: 1, workers: 3, pattern: "machine" },
];

function ranking(days: number) {
  const weights = { production: 50, quality: 30, time: 20 };
  const rows = NAMES.slice(0, 8).map((name, i) => {
    const eff = 92 - i * 4;
    const fp = 98 - i;
    const prod = 90 - i * 3;
    const scores = { production: eff, quality: fp, time: prod };
    return {
      worker: { id: i + 1, name, code: `W${100 + i}` },
      operation: { id: (i % OPS.length) + 1, name: OPS[i % OPS.length][0], smv: OPS[i % OPS.length][1] },
      line_id: (i % 3) + 1, comparison_group: OPS[i % OPS.length][0],
      efficiency_pct: eff, first_pass_pct: fp, productive_pct: prod, coverage_pct: 96,
      eligible: true, exclusion_reason: null, scores,
      contributions: { production: eff * 0.5, quality: fp * 0.3, time: prod * 0.2 },
      total: Math.round((eff * 0.5 + fp * 0.3 + prod * 0.2) * 10) / 10, rank: i + 1,
    };
  });
  return {
    period: { days, start: iso(days * 1440), end: iso(0) },
    policy: { version_id: 1, version: 1, effective_from: null, weights, min_coverage_pct: 70, period_days: days },
    policy_version_id: 1, group: null, groups: [], bonus_enabled: false, rows,
  };
}

function timeline(stationId: number) {
  const seg = (state: string, s: number, e: number | null, id: number) => ({ state, start: iso(s), end: e === null ? null : iso(e), event_id: id, review_status: "none" });
  return {
    station: { id: stationId, code: `S${stationId}`, line: "Line 1 · Shirts" },
    worker: { id: 1, name: NAMES[0] },
    operation: { name: OPS[0][0], smv: OPS[0][1] },
    shift,
    lanes: {
      worker_state: [seg("working", 240, 120, 1), seg("away", 120, 110, 2), seg("working", 110, null, 3)],
      machine_state: [seg("running", 240, 125, 4), seg("idle", 125, 110, 5), seg("running", 110, null, 6)],
    },
    minutes: { working: 220, away: 10, idle: 15 },
    output: 96,
    efficiency_pct: 71.4,
  };
}

const RULES = [
  { id: 1, name: "Machine down", kind: "machine_down", condition: { minutes: 10 }, severity: "critical", recipient_roles: ["factory_admin", "maintenance"], is_enabled: true },
  { id: 2, name: "Long idle", kind: "idle", condition: { minutes: 5 }, severity: "warning", recipient_roles: ["supervisor"], is_enabled: true },
];

// ---------- setup / structure / policies / cameras / reports ----------
const FACTORY = { id: 1, code: "DEMO", name: "Demo Garments Ltd", timezone: "Asia/Dhaka", settings: { card_tap_enabled: false, face_blur: true } };
const FLOORS = [{ id: 1, factory_id: 1, code: "F1", name: "Floor 1" }];
const LINE_ROWS = LINES.map((l) => ({ id: l.id, floor_id: 1, code: l.code, name: l.name, is_active: true }));
const STATION_ROWS = LINES.flatMap((l) =>
  Array.from({ length: l.stations }, (_, i) => ({
    id: l.id * 100 + i + 1, line_id: l.id, code: `${l.code}-S${String(i + 1).padStart(2, "0")}`,
    name: `Station ${i + 1}`, position: i + 1, status: "active",
  })),
);
const MACHINE_TYPES = [
  { id: 1, code: "SNLS", name: "Single needle lockstitch", name_bn: null, is_active: true },
  { id: 2, code: "OL", name: "Overlock", name_bn: null, is_active: true },
];
const BRANDS = [{ id: 1, name: "Juki", is_active: true }, { id: 2, name: "Brother", is_active: true }, { id: 3, name: "Jack", is_active: true }];
const PRODUCTS = [{ id: 1, code: "SHIRT", name: "Basic shirt" }, { id: 2, code: "POLO", name: "Polo" }];
const OPERATIONS = OPS.map(([name, smv], i) => ({
  id: i + 1, product_id: 1, code: `OP${i + 1}`, name, name_bn: null, smv, difficulty_group: i < 3 ? "medium" : "easy",
}));
const REASONS = [
  { id: 1, category: "downtime", code: "NEEDLE", name: "Needle break", name_bn: null, is_active: true },
  { id: 2, category: "downtime", code: "THREAD", name: "Thread problem", name_bn: null, is_active: true },
  { id: 3, category: "reject", code: "SKIP", name: "Skipped stitch", name_bn: null, is_active: true },
];
const MACHINES = STATION_ROWS.slice(0, 12).map((s, i) => ({
  id: i + 1, factory_id: 1, asset_code: `M-${1000 + i}`, machine_type: MACHINE_TYPES[i % 2].name, brand: BRANDS[i % 3].name,
  model: i % 2 ? "MO-6900" : "DDL-8700", status: "active", station: { id: s.id, code: s.code, line_id: s.line_id },
}));
const WORKERS = NAMES.map((n, i) => ({ id: i + 1, employee_code: `E${100 + i}`, full_name: n, full_name_bn: null, factory_id: 1, rfid_card_id: null, is_active: true }));
const ASSIGNMENTS = NAMES.map((n, i) => ({
  id: i + 1, worker_id: i + 1, station_id: STATION_ROWS[i].id, operation_id: (i % OPS.length) + 1, valid_from: iso(60 * 24 * 30), valid_to: null,
  worker: { id: i + 1, employee_code: `E${100 + i}`, full_name: n },
  station: { id: STATION_ROWS[i].id, code: STATION_ROWS[i].code, line_id: STATION_ROWS[i].line_id },
  operation: { id: (i % OPS.length) + 1, code: `OP${(i % OPS.length) + 1}`, name: OPS[i % OPS.length][0] },
}));
const USER_ROWS = Object.entries(USERS).map(([email, u]) => ({
  id: u.id, email, full_name: u.full_name, locale: "en", is_active: true, created_at: iso(60 * 24 * 60),
  roles: [{ role: u.role, scope_type: "factory", scope_id: 1 }],
}));
const ver = (version: number, body: Record<string, unknown>) => ({ version, body, effective_from: iso(60 * 24 * 14), effective_to: null });
const POLICIES = [
  { kind: "shift", name: "Shift", current: ver(1, { start: "08:00", end: "17:00", breaks: [{ start: "12:30", end: "13:30" }] }), scheduled: null, history: [] },
  { kind: "thresholds", name: "Thresholds", current: ver(1, { target_efficiency_pct: 65, down_after_min: 10, idle_after_min: 5 }), scheduled: null, history: [] },
  { kind: "retention", name: "Retention", current: ver(1, { events_days: 180, audit_days: 365 }), scheduled: null, history: [] },
];
const EDGE_BOXES = [{ id: 1, code: "EDGE-1", name: "Floor 1 edge box", online: true, last_seen_at: iso(1) }];
const CAMERAS = [1, 2, 3].map((n) => ({
  id: n, code: `CAM-${n}`, name: `Line ${n} camera`, edge_box_id: 1,
  stations: STATION_ROWS.filter((s) => s.line_id === n).slice(0, 4).map((s) => ({ id: s.id, code: s.code })),
  purpose: "activity", fps: 5, face_blur: true, zones: [], zones_count: 4, connection: null, online: true, last_seen_at: iso(0), is_active: true,
}));
const REVIEW_ITEMS = [
  { id: 1, event_type: "phone_use", state: "phone_use", title: "Possible phone use", station: { id: 304, code: "L3-S04" }, line: { id: 3, name: "Line 3 · Polo" }, worker: { id: 4, name: NAMES[3] }, start_time: iso(47), duration_s: 95, confidence: 0.58, source: "vision", model_version: "demo-1" },
  { id: 2, event_type: "needle_break", state: "needle_break", title: "Needle break suspected", station: { id: 105, code: "L1-S05" }, line: { id: 1, name: "Line 1 · Shirts" }, worker: null, start_time: iso(32), duration_s: null, confidence: 0.71, source: "vision", model_version: "demo-1" },
];
const AUDIT = ["policy.update", "user.create", "alert.ack"].map((action, i) => ({
  id: 10 - i, at: iso(30 * (i + 1)), actor: { id: 1, name: "Demo Admin", email: "admin@stitchsense.local" },
  action, entity: action.split(".")[0], entity_id: String(i + 1), detail: null, ip: "127.0.0.1",
}));
const DAY_REPORT = (lineId: number) => {
  const line = LINES.find((l) => l.id === lineId) ?? LINES[0];
  return {
    date: iso(0).slice(0, 10), timezone: "Asia/Dhaka", partial: false,
    line: { id: line.id, code: line.code, name: line.name }, generated_at: iso(0),
    workers: NAMES.slice(0, 8).map((n, i) => ({
      worker: { id: i + 1, name: n, code: `E${100 + i}` }, operation: OPS[i % OPS.length][0],
      accepted: 410 - i * 12, rework: 6 + i, rejected: 2, efficiency_pct: 88 - i * 3, first_pass_pct: 97 - i,
      attended_min: 480, downtime_min: 10 + i * 2, coverage_pct: 96, state_min: { working: 410 - i * 6, idle: 20, away: 10 },
    })),
    stations: [{ code: `${line.code}-S08`, stops: 3, down_min: 38 }, { code: `${line.code}-S05`, stops: 1, down_min: 9 }],
    totals: { accepted: 3100, rework: 52, rejected: 16, stops: 4, down_min: 47 },
  };
};

const GET_ROUTES: [RegExp, (m: RegExpMatchArray, q: URLSearchParams) => unknown][] = [
  [/^\/performance\/workers\/(\d+)$/, (m, q) => {
    const r = ranking(Number(q.get("days")) || 7);
    const row = r.rows.find((x) => x.worker.id === Number(m[1])) ?? r.rows[0];
    const src = { production: "Output vs target (SMV)", quality: "First-pass share", time: "Productive share of attended time" };
    const unit = { production: "%", quality: "%", time: "%" };
    const label = { production: "Production", quality: "Quality", time: "Productive time" };
    const keys = ["production", "quality", "time"] as const;
    return {
      ...row, period: r.period, policy_version_id: 1, bonus_enabled: false,
      components: keys.map((k) => ({ key: k, label: label[k], value: row.scores[k], unit: unit[k], score: row.scores[k], weight: r.policy.weights[k], contribution: row.contributions[k], source: src[k] })),
      excluded: { downtime_min: 38, rejected_min: { skipped_stitch: 6 }, break_min: 60, scheduled_min: 540 },
    };
  }],
  [/^\/policies$/, () => POLICIES],
  [/^\/floors$/, () => FLOORS],
  [/^\/lines$/, () => LINE_ROWS],
  [/^\/stations$/, (_m, q) => (q.get("line_id") ? STATION_ROWS.filter((s) => s.line_id === Number(q.get("line_id"))) : STATION_ROWS)],
  [/^\/catalog\/machine-types$/, () => MACHINE_TYPES],
  [/^\/catalog\/machine-brands$/, () => BRANDS],
  [/^\/catalog\/reason-codes$/, () => REASONS],
  [/^\/products$/, () => PRODUCTS],
  [/^\/operations$/, () => OPERATIONS],
  [/^\/machines$/, () => MACHINES],
  [/^\/workers$/, () => WORKERS],
  [/^\/workers\/(\d+)$/, (m) => WORKERS.find((w) => w.id === Number(m[1])) ?? WORKERS[0]],
  [/^\/assignments$/, () => ASSIGNMENTS],
  [/^\/users$/, () => USER_ROWS],
  [/^\/edge-boxes$/, () => EDGE_BOXES],
  [/^\/cameras$/, () => CAMERAS],
  [/^\/cameras\/live$/, () => CAMERAS.map((c) => ({ id: c.id, code: c.code, name: c.name, stations: c.stations, online: true, privacy_zones: 2, live: { mode: "demo", url: null } }))],
  [/^\/cameras\/station-options$/, () => LINES.map((l) => ({ id: l.id, code: l.code, name: l.name, stations: STATION_ROWS.filter((s) => s.line_id === l.id).map((s) => ({ id: s.id, code: s.code, name: s.name })) }))],
  [/^\/events\/review-queue$/, () => REVIEW_ITEMS],
  [/^\/audit-logs$/, () => AUDIT],
  [/^\/reports\/day$/, (_m, q) => DAY_REPORT(Number(q.get("line_id")) || 1)],
  [/^\/auth\/me$/, () => currentMe()],
  [/^\/overview$/, () => overview()],
  [/^\/floor$/, (_m, q) => floor(Number(q.get("line_id")) || 1)],
  [/^\/org\/tree$/, () => [{ id: 1, name: "Demo Garments Ltd", floors: [{ id: 1, name: "Floor 1", lines: LINES }] }]],
  [/^\/stations\/(\d+)\/timeline$/, (m) => timeline(Number(m[1]))],
  [/^\/alerts$/, (_m, q) => ALERTS.slice(0, Number(q.get("limit")) || ALERTS.length)],
  [/^\/alert-rules$/, () => RULES],
  [/^\/needles\/stats$/, () => NEEDLES],
  [/^\/performance$/, (_m, q) => ranking(Number(q.get("days")) || 7)],
  [/^\/simulator$/, () => ({ running: true })],
  [/^\/factories$/, () => [FACTORY]],
];

/** Same contract as `api()`: resolves `{data, meta}` or throws `{status, code, message}`. */
export function mockApi(path: string, method: string, body: unknown): { data: unknown; meta: Record<string, unknown> } {
  const [pathname, query = ""] = path.split("?");
  if (method === "POST" && pathname === "/auth/login") {
    const { email = "", password = "" } = (body ?? {}) as { email?: string; password?: string };
    const key = String(email).toLowerCase();
    if (!USERS[key] || password !== DEMO_PASSWORD) throw new MockError(401, "INVALID_CREDENTIALS", "Wrong email or password.");
    sessionStorage.setItem(SESSION_KEY, key);
    return { data: currentMe(), meta: {} };
  }
  if (method === "POST" && pathname === "/auth/logout") {
    sessionStorage.removeItem(SESSION_KEY);
    return { data: null, meta: {} };
  }
  if (method !== "GET") return { data: { ok: true }, meta: {} }; // demo is read-only; writes are accepted and ignored
  for (const [re, fn] of GET_ROUTES) {
    const m = pathname.match(re);
    if (m) return { data: fn(m, new URLSearchParams(query)), meta: { total: 0 } };
  }
  return { data: [], meta: { total: 0 } }; // unknown lists render their empty state
}

export { MockError };
