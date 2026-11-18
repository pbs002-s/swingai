"use client";

import Link from "next/link";
import { useState } from "react";
import { ApiFailure, api, post } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { Empty, ErrorBox, Loading } from "@/components/app/ui";
import type { Camera, DetectionResult, LineOption, WizardDraft } from "@/lib/types-cameras";
import { Field, Snapshot } from "./parts";
import { JobProgress, useEdgeJob } from "./useEdgeJob";

type StepProps = { draft: WizardDraft; update: (patch: Partial<WizardDraft>) => void };
const MAX_STATIONS = 2;

export function StepAssign({ draft, update }: StepProps) {
  const lines = useApi<LineOption[]>("/cameras/station-options");
  if (lines.error) return <ErrorBox message={lines.error.message} onRetry={lines.refresh} />;
  if (lines.loading && !lines.data) return <Loading />;
  if (!lines.data?.length) return <Empty title="No lines yet" text="Create lines and stations in setup before adding cameras." />;
  const line = lines.data.find((l) => l.id === draft.lineId);
  const picked = new Set(draft.stations.map((s) => s.id));

  return (
    <div className="flex flex-col gap-4">
      <Field label="Line">
        {(id) => (
          <select
            id={id}
            className="field max-w-[320px]"
            value={draft.lineId ?? ""}
            onChange={(e) => update({ lineId: Number(e.target.value) || null, stations: [], zones: [] })}
          >
            <option value="">Choose a line</option>
            {lines.data!.map((l) => <option key={l.id} value={l.id}>{l.name} ({l.code})</option>)}
          </select>
        )}
      </Field>
      {line && (
        <fieldset>
          <legend className="mb-2 text-[14px] text-ink-2">Pick one or two stations this camera sees ({draft.stations.length} of {MAX_STATIONS} chosen).</legend>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
            {line.stations.map((s) => {
              const on = picked.has(s.id);
              const full = !on && draft.stations.length >= MAX_STATIONS;
              const toggle = () =>
                update({
                  stations: on ? draft.stations.filter((x) => x.id !== s.id) : [...draft.stations, s],
                  zones: draft.zones.filter((z) => z.kind === "privacy" || z.station_id !== s.id),
                });
              return (
                <label key={s.id} className={`flex min-h-11 items-center gap-2 rounded-lg border px-3 text-[14px] ${on ? "border-brand bg-brand-bg" : "border-line"} ${full ? "opacity-50" : "cursor-pointer"}`}>
                  <input type="checkbox" checked={on} disabled={full} onChange={toggle} className="size-4 accent-[var(--brand)]" />
                  <span className="font-mono">{s.code}</span>
                </label>
              );
            })}
          </div>
        </fieldset>
      )}
    </div>
  );
}

export function StepSettings({ draft, update }: StepProps) {
  return (
    <div className="flex max-w-[560px] flex-col gap-5">
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-[13px] font-medium">Purpose</legend>
        {(
          [
            ["activity", "Worker activity", "Working, away and phone use at the station."],
            ["seam_inspection", "Seam inspection", "Skipped stitches, puckering and flagging on the seam."],
          ] as const
        ).map(([value, label, hint]) => (
          <label key={value} className="flex min-h-11 cursor-pointer items-start gap-2 py-1">
            <input type="radio" name="purpose" checked={draft.purpose === value} onChange={() => update({ purpose: value })} className="mt-1 size-4 accent-[var(--brand)]" />
            <span className="flex flex-col">
              <span className="text-[14px]">{label}</span>
              <span className="text-[12px] text-ink-3">{hint}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <Field label="Analysis rate (frames per second)" hint="1 to 15. 5 is enough for activity; seam inspection may need more.">
        {(id) => (
          <input id={id} className="field w-28" type="number" min={1} max={15} value={draft.fps} onChange={(e) => update({ fps: Math.min(15, Math.max(1, Math.round(Number(e.target.value) || 1))) })} />
        )}
      </Field>
      <label className="flex min-h-11 cursor-pointer items-start gap-2">
        <input type="checkbox" checked={draft.faceBlur} onChange={(e) => update({ faceBlur: e.target.checked })} className="mt-1 size-4 accent-[var(--brand)]" />
        <span className="flex flex-col">
          <span className="text-[14px]">Blur faces in evidence images</span>
          <span className="text-[12px] text-ink-3">On by default. Faces are never recognised, only blurred.</span>
        </span>
      </label>
    </div>
  );
}

type SaveState = { phase: "idle" | "saving" | "saved"; camera: Camera | null; error: string | null };

export function StepVerify({ draft }: { draft: WizardDraft }) {
  const [save, setSave] = useState<SaveState>({ phase: "idle", camera: null, error: null });
  const detect = useEdgeJob<DetectionResult>();
  const boxId = draft.edgeBoxId;

  async function saveAndVerify() {
    if (boxId == null) return;
    setSave((s) => ({ ...s, phase: "saving", error: null }));
    try {
      let camera = save.camera; // never create twice if a later step failed
      if (!camera) {
        camera = (
          await post<Camera>("/cameras", {
            edge_box_id: boxId,
            name: draft.name.trim() || "Camera",
            connection: draft.connection,
            station_ids: draft.stations.map((s) => s.id),
            purpose: draft.purpose,
            fps: draft.fps,
            face_blur: draft.faceBlur,
          })
        ).data;
        setSave({ phase: "saving", camera, error: null });
      }
      camera = (await api<Camera>(`/cameras/${camera.id}/zones`, { method: "PUT", body: JSON.stringify({ zones: draft.zones }) })).data;
      setSave({ phase: "saved", camera, error: null });
      await detect.run(boxId, "test_detection", { camera_id: camera.id });
    } catch (e) {
      setSave((s) => ({ ...s, phase: "idle", error: e instanceof ApiFailure ? e.message : "Could not save the camera." }));
    }
  }

  const summary: [string, string][] = [
    ["Name", draft.name.trim() || "Camera"],
    ["Address", `${draft.connection.host}:${draft.connection.port}${draft.connection.rtsp_path}`],
    ["Stations", draft.stations.map((s) => s.code).join(", ")],
    ["Zones", `${draft.zones.filter((z) => z.kind === "work").length} work, ${draft.zones.filter((z) => z.kind === "privacy").length} privacy`],
    ["Purpose", draft.purpose === "activity" ? "Worker activity" : "Seam inspection"],
    ["Analysis rate", `${draft.fps} fps`],
    ["Face blur", draft.faceBlur ? "On" : "Off"],
  ];
  const result = detect.phase === "done" ? detect.job?.result : null;

  return (
    <div className="flex flex-col gap-5">
      <dl className="grid gap-x-6 gap-y-2 text-[14px] sm:grid-cols-2" aria-label="Camera summary">
        {summary.map(([k, v]) => (
          <div key={k} className="flex gap-3">
            <dt className="w-28 shrink-0 text-ink-3">{k}</dt>
            <dd className="font-medium">{v}</dd>
          </div>
        ))}
      </dl>
      {save.phase !== "saved" && (
        <div>
          <button type="button" className="btn btn-brand" disabled={save.phase === "saving"} onClick={saveAndVerify}>
            {save.phase === "saving" ? "Saving…" : save.camera ? "Try saving again" : "Save and run test detection"}
          </button>
        </div>
      )}
      {save.error && <ErrorBox message={save.error} />}
      {save.phase === "saved" && save.camera && (
        <p role="status" className="text-[14px] text-run">
          Saved as <span className="font-mono">{save.camera.code}</span>. The edge box picks up the new settings on its next poll.
        </p>
      )}
      <JobProgress phase={detect.phase} label="Running a 30-second test detection…" />
      {detect.error && (
        <ErrorBox message={`Test detection failed: ${detect.error}`} onRetry={() => save.camera && boxId != null && detect.run(boxId, "test_detection", { camera_id: save.camera.id })} />
      )}
      {result && (
        <section aria-labelledby="verify-h" className="flex flex-col gap-3">
          <h3 id="verify-h" className="text-[15px] font-semibold">Test detection</h3>
          <Snapshot src={result.snapshot} alt={`Annotated snapshot: ${result.detections.map((d) => d.label).join(", ") || "nothing detected"}`} />
          <ul className="flex flex-wrap gap-3 text-[14px]" aria-label="Detections">
            {result.detections.map((d, i) => (
              <li key={i} className="rounded-md border border-line px-2 py-1">
                {d.label} <span className="font-mono text-ink-3">{Math.round(d.confidence * 100)}% confidence</span>
              </li>
            ))}
          </ul>
          <p className="text-[12px] text-ink-3">Detections are suggestions with a confidence, not confirmed facts.</p>
          <div>
            <Link href="/app/cameras" className="btn btn-primary">Done, back to cameras</Link>
          </div>
        </section>
      )}
    </div>
  );
}
