"use client";

import { useEffect, useState } from "react";
import { ApiFailure, api } from "@/lib/api";
import { ErrorBox } from "@/components/app/ui";
import type { Camera, TestResult, Zone } from "@/lib/types-cameras";
import { ZoneEditor } from "./ZoneEditor";
import { JobProgress, useEdgeJob } from "./useEdgeJob";

/** Edit a saved camera's zones on a fresh snapshot from its edge box. */
export function CameraZonesPanel({ camera, onSaved, onClose }: { camera: Camera; onSaved: () => void; onClose: () => void }) {
  const [zones, setZones] = useState<Zone[]>(camera.zones);
  const [state, setState] = useState<{ saving: boolean; error: string | null; saved: boolean }>({ saving: false, error: null, saved: false });
  const snap = useEdgeJob<TestResult>();
  const { run } = snap;
  const boxId = camera.edge_box_id;

  useEffect(() => {
    if (boxId != null) void run(boxId, "snapshot", { camera_id: camera.id });
  }, [boxId, camera.id, run]);

  async function save() {
    setState({ saving: true, error: null, saved: false });
    try {
      await api(`/cameras/${camera.id}/zones`, { method: "PUT", body: JSON.stringify({ zones }) });
      setState({ saving: false, error: null, saved: true });
      onSaved();
    } catch (e) {
      setState({ saving: false, error: e instanceof ApiFailure ? e.message : "Could not save the zones.", saved: false });
    }
  }

  return (
    <section aria-label={`Zones for ${camera.name}`} className="flex flex-col gap-4 border-t border-line bg-surface px-5 py-4">
      {boxId == null && <p className="text-[13px] text-ink-3">This camera is not linked to an edge box, so there is no live snapshot. Zones can still be drawn.</p>}
      <JobProgress phase={snap.phase} label="Fetching a snapshot from the edge box…" />
      {snap.error && <ErrorBox message={`No snapshot: ${snap.error}`} onRetry={() => boxId != null && run(boxId, "snapshot", { camera_id: camera.id })} />}
      <ZoneEditor snapshot={snap.job?.result?.snapshot} stations={camera.stations.map((s) => ({ ...s, name: s.code }))} zones={zones} onChange={setZones} />
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className="btn btn-brand" disabled={state.saving} onClick={save}>{state.saving ? "Saving…" : "Save zones"}</button>
        <button type="button" className="btn btn-ghost" onClick={onClose}>Close</button>
        {state.saved && <span role="status" className="text-[13px] text-run">Zones saved.</span>}
        {state.error && <span role="alert" className="text-[13px] text-down">{state.error}</span>}
      </div>
    </section>
  );
}
