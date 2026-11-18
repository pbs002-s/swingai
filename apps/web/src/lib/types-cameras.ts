/** Shapes for the cameras and edge job API (apps/api/app/modules/cameras.py). */

export type EdgeBox = { id: number; code: string; name: string; online: boolean; last_seen_at: string | null };

export type Connection = { host: string; port: number; rtsp_path: string; username: string; password: string };
export type PublicConnection = Omit<Connection, "password"> & { has_password: boolean };

export type ZoneKind = "work" | "privacy";
export type Point = [number, number];
export type Zone = { station_id: number | null; kind: ZoneKind; points: Point[] };

export type Purpose = "activity" | "seam_inspection";

export type Camera = {
  id: number;
  code: string;
  name: string;
  edge_box_id: number | null;
  stations: { id: number; code: string }[];
  purpose: Purpose;
  fps: number;
  face_blur: boolean;
  zones: Zone[];
  zones_count: number;
  connection: PublicConnection | null;
  online: boolean;
  last_seen_at: string | null;
  is_active: boolean;
};

export type JobKind = "discover_cameras" | "test_camera" | "snapshot" | "test_detection";
export type JobStatus = "queued" | "running" | "done" | "failed";

export type DiscoveredCamera = { brand: string; model: string; host: string; port: number; rtsp_path: string; onvif: boolean };
export type TestResult = { resolution: string; width: number; height: number; fps: number; codec: string; latency_ms: number; snapshot: string };
export type Detection = { label: string; confidence: number; box: [number, number, number, number] };
export type DetectionResult = { snapshot: string; detections: Detection[]; duration_s: number; fps: number };

export type EdgeJob<R = Record<string, unknown>> = {
  id: number;
  edge_box_id: number;
  kind: JobKind;
  status: JobStatus;
  result: R | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
};

export type StationOption = { id: number; code: string; name: string };
export type LineOption = { id: number; code: string; name: string; stations: StationOption[] };

/** Everything the Add camera wizard collects before it saves. */
export type WizardDraft = {
  edgeBoxId: number | null;
  name: string;
  connection: Connection;
  test: TestResult | null;
  lineId: number | null;
  stations: StationOption[];
  zones: Zone[];
  purpose: Purpose;
  fps: number;
  faceBlur: boolean;
};
