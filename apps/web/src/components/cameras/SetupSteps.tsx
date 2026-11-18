"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/hooks";
import { Empty, ErrorBox, Loading, minutesSince } from "@/components/app/ui";
import type { DiscoveredCamera, EdgeBox, TestResult, WizardDraft } from "@/lib/types-cameras";
import { ConnectionForm, Field, Snapshot } from "./parts";
import { JobProgress, useEdgeJob } from "./useEdgeJob";

type StepProps = { draft: WizardDraft; update: (patch: Partial<WizardDraft>) => void };

export function StepEdgeBox({ draft, update }: StepProps) {
  const boxes = useApi<EdgeBox[]>("/edge-boxes", 10_000);
  if (boxes.error) return <ErrorBox message={boxes.error.message} onRetry={boxes.refresh} />;
  if (boxes.loading && !boxes.data) return <Loading />;
  if (!boxes.data?.length) return <Empty title="No edge boxes yet" text="Install and register an edge box on this floor first. Cameras connect through it." />;
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-[14px] text-ink-2">Choose the edge box on the same network as the camera. Only online boxes can be used.</legend>
      {boxes.data.map((b) => (
        <label
          key={b.id}
          className={`flex min-h-14 items-center gap-3 rounded-xl border px-4 ${draft.edgeBoxId === b.id ? "border-brand bg-brand-bg" : "border-line"} ${b.online ? "cursor-pointer" : "opacity-60"}`}
        >
          <input
            type="radio"
            name="edge-box"
            disabled={!b.online}
            checked={draft.edgeBoxId === b.id}
            onChange={() => update({ edgeBoxId: b.id, test: null })}
            className="size-4 accent-[var(--brand)]"
          />
          <span className="flex flex-1 flex-col">
            <span className="text-[14px] font-medium">{b.name}</span>
            <span className="font-mono text-[12px] text-ink-3">{b.code}</span>
          </span>
          <span className={`flex items-center gap-1.5 text-[13px] ${b.online ? "text-run" : "text-ink-3"}`}>
            <span className={`size-2 rounded-full ${b.online ? "bg-run" : "bg-off"}`} aria-hidden="true" />
            {b.online ? "Online" : `Offline${b.last_seen_at ? `, last seen ${minutesSince(b.last_seen_at)} ago` : ""}`}
          </span>
        </label>
      ))}
    </fieldset>
  );
}

export function StepFind({ draft, update }: StepProps) {
  const [mode, setMode] = useState<"scan" | "manual">("scan");
  const scan = useEdgeJob<{ cameras: DiscoveredCamera[] }>();
  const found = scan.job?.result?.cameras ?? [];

  function choose(c: DiscoveredCamera) {
    update({
      connection: { ...draft.connection, host: c.host, port: c.port, rtsp_path: c.rtsp_path },
      name: draft.name || `${c.brand} ${c.model}`,
      test: null,
    });
    setMode("manual");
  }

  return (
    <div className="flex flex-col gap-5">
      <div role="group" aria-label="How to find the camera" className="flex flex-wrap gap-2">
        <button type="button" className={`btn ${mode === "scan" ? "btn-primary" : "btn-ghost"}`} aria-pressed={mode === "scan"} onClick={() => setMode("scan")}>
          Scan network
        </button>
        <button type="button" className={`btn ${mode === "manual" ? "btn-primary" : "btn-ghost"}`} aria-pressed={mode === "manual"} onClick={() => setMode("manual")}>
          Enter manually
        </button>
      </div>

      {mode === "scan" && (
        <section aria-label="Network scan" className="flex flex-col gap-3">
          <p className="text-[14px] text-ink-2">The edge box looks for ONVIF cameras on its network. Cameras without ONVIF must be entered manually.</p>
          <div>
            <button type="button" className="btn btn-brand" disabled={scan.phase === "waiting" || draft.edgeBoxId == null} onClick={() => draft.edgeBoxId && scan.run(draft.edgeBoxId, "discover_cameras")}>
              {scan.phase === "done" ? "Scan again" : "Start scan"}
            </button>
          </div>
          <JobProgress phase={scan.phase} label="Scanning the camera network…" />
          {scan.error && <ErrorBox message={scan.error} />}
          {scan.phase === "done" && found.length === 0 && <Empty title="No cameras found" text="Check the camera is powered and on the camera network, or enter it manually." />}
          {found.length > 0 && (
            <ul aria-label="Cameras found" className="flex flex-col divide-y divide-line rounded-xl border border-line">
              {found.map((c) => (
                <li key={c.host} className="flex flex-wrap items-center gap-3 px-4 py-2">
                  <span className="flex flex-1 flex-col">
                    <span className="text-[14px] font-medium">{c.brand} {c.model}</span>
                    <span className="font-mono text-[12px] text-ink-3">{c.host}:{c.port}</span>
                  </span>
                  <button type="button" className="btn btn-ghost" aria-label={`Use ${c.brand} ${c.model} at ${c.host}`} onClick={() => choose(c)}>
                    Use this camera
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {mode === "manual" && (
        <section aria-label="Camera connection" className="flex flex-col gap-4">
          <Field label="Camera name" hint="Shown in lists and alerts, for example Line 1 stations 1-2">
            {(id) => <input id={id} className="field" value={draft.name} maxLength={80} onChange={(e) => update({ name: e.target.value })} />}
          </Field>
          <ConnectionForm value={draft.connection} onChange={(connection) => update({ connection, test: null })} />
        </section>
      )}
    </div>
  );
}

export function StepTest({ draft, update }: StepProps) {
  const test = useEdgeJob<TestResult>();
  const result = draft.test;

  async function run() {
    update({ test: null });
    if (draft.edgeBoxId) await test.run(draft.edgeBoxId, "test_camera", { connection: draft.connection });
  }
  const finished = test.phase === "done" ? test.job?.result ?? null : null;
  useEffect(() => {
    if (finished) update({ test: finished });
  }, [finished, update]);

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[14px] text-ink-2">
        The edge box opens the stream at <span className="font-mono">{draft.connection.host}:{draft.connection.port}</span> and sends back one frame.
      </p>
      <div>
        <button type="button" className="btn btn-brand" disabled={test.phase === "waiting"} onClick={run}>
          {result ? "Test again" : "Test connection"}
        </button>
      </div>
      <JobProgress phase={test.phase} label="Opening the camera stream…" />
      {test.error && <ErrorBox message={`Connection test failed: ${test.error}`} onRetry={run} />}
      {result && (
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_220px]">
          <Snapshot src={result.snapshot} alt="Snapshot from the camera under test" />
          <dl className="grid grid-cols-2 content-start gap-x-4 gap-y-2 text-[14px] md:grid-cols-1" aria-label="Stream details">
            {[
              ["Resolution", result.resolution],
              ["Frame rate", `${result.fps} fps`],
              ["Codec", result.codec],
              ["Latency", `${result.latency_ms} ms`],
            ].map(([k, v]) => (
              <div key={k}>
                <dt className="text-[12px] text-ink-3">{k}</dt>
                <dd className="font-mono">{v}</dd>
              </div>
            ))}
          </dl>
          <p role="status" className="text-[14px] text-run md:col-span-2">Connection works.</p>
        </div>
      )}
    </div>
  );
}
