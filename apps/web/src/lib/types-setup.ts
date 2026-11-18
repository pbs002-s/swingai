/** Shapes returned by the setup endpoints (apps/api/app/modules/setup.py, setup_users.py, imports.py). */

export type FactorySettings = { card_tap_enabled?: boolean | null; face_blur?: boolean | null };
export type Factory = { id: number; code: string; name: string; timezone: string; settings: FactorySettings };
export type FloorRow = { id: number; factory_id: number; code: string; name: string };
export type LineRow = { id: number; floor_id: number; code: string; name: string; is_active: boolean };
export type StationStatus = "active" | "maintenance" | "inactive";
export type StationRow = { id: number; line_id: number; code: string; name: string; position: number; status: StationStatus };

export type MachineType = { id: number; code: string; name: string; name_bn: string | null; is_active: boolean };
export type MachineBrand = { id: number; name: string; is_active: boolean };
export type ReasonCategory = "downtime" | "pause" | "reject";
export type ReasonCode = { id: number; category: ReasonCategory; code: string; name: string; name_bn: string | null; is_active: boolean };
export type Product = { id: number; code: string; name: string };
export type Operation = {
  id: number;
  product_id: number;
  code: string;
  name: string;
  name_bn: string | null;
  smv: number;
  difficulty_group: string;
};

export type MachineRow = {
  id: number;
  factory_id: number;
  asset_code: string;
  machine_type: string;
  brand: string;
  model: string | null;
  status: StationStatus;
  station: { id: number; code: string; line_id: number } | null;
};

export type WorkerListRow = { id: number; employee_code: string; full_name: string; full_name_bn: string | null };
export type WorkerRow = WorkerListRow & { factory_id: number; rfid_card_id: string | null; is_active: boolean };

export type AssignmentRow = {
  id: number;
  worker_id: number;
  station_id: number;
  operation_id: number;
  valid_from: string;
  valid_to: string | null;
  worker: { id: number; employee_code: string; full_name: string };
  station: { id: number; code: string; line_id: number };
  operation: { id: number; code: string; name: string };
};

export type ScopeType = "all" | "factory" | "line";
export type UserRoleRow = { role: string; scope_type: ScopeType; scope_id: number | null };
export type UserRow = {
  id: number;
  email: string;
  full_name: string;
  locale: "en" | "bn";
  is_active: boolean;
  created_at: string;
  roles: UserRoleRow[];
};

export type ImportKind = "org" | "machines" | "workers" | "operations" | "needle-batches" | "attendance";
export type ImportResult = {
  kind: ImportKind;
  create: number;
  update: number;
  errors: { row: number; column: string; message: string }[];
  error_count: number;
  committed: boolean;
};
