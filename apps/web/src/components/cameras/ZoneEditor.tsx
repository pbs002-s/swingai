"use client";

import { useState } from "react";
import type { MouseEvent } from "react";
import type { Point, StationOption, Zone, ZoneKind } from "@/lib/types-cameras";
import { Field, safeSnapshot } from "./parts";

const MAX_POINTS = 32;
const MAX_ZONES = 24;
const VB_W = 640;
const VB_H = 360;
const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const pctText = (v: number) => `${Math.round(v * 100)}%`;
const polyPoints = (pts: Point[]) => pts.map(([x, y]) => `${x * VB_W},${y * VB_H}`).join(" ");

type Props = {
  snapshot: string | null | undefined;
  stations: StationOption[];
  zones: Zone[];
  onChange: (zones: Zone[]) => void;
};

/** Draw work zones and privacy masks on a snapshot. Click to add points, or type them in (keyboard). */
export function ZoneEditor({ snapshot, stations, zones, onChange }: Props) {
  const [draft, setDraft] = useState<Point[]>([]);
  const [kind, setKind] = useState<ZoneKind>("work");
  const [stationId, setStationId] = useState<number | null>(stations[0]?.id ?? null);
  const [typed, setTyped] = useState({ x: "50", y: "50" });
  const src = safeSnapshot(snapshot);
  const stationCode = (id: number | null) => stations.find((s) => s.id === id)?.code ?? "unknown station";
  const zoneLabel = (z: Zone) => (z.kind === "privacy" ? "Privacy mask" : `Work zone for ${stationCode(z.station_id)}`);

  const addPoint = (p: Point) => setDraft((d) => (d.length >= MAX_POINTS ? d : [...d, p]));
  function handleClick(e: MouseEvent<SVGSVGElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    addPoint([clamp01((e.clientX - r.left) / r.width), clamp01((e.clientY - r.top) / r.height)]);
  }
  function addTyped() {
    const x = Number(typed.x) / 100;
    const y = Number(typed.y) / 100;
    if (Number.isFinite(x) && Number.isFinite(y)) addPoint([clamp01(x), clamp01(y)]);
  }
  function closePolygon() {
    if (draft.length < 3 || zones.length >= MAX_ZONES) return;
    const round = (v: number) => Math.round(v * 1000) / 1000;
    onChange([...zones, { kind, station_id: kind === "work" ? stationId : null, points: draft.map(([x, y]) => [round(x), round(y)]) }]);
    setDraft([]);
  }
  const canClose = draft.length >= 3 && zones.length < MAX_ZONES && (kind === "privacy" || stationId != null);

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="flex flex-col gap-2">
        <div className="relative overflow-hidden rounded-xl border border-line bg-sunk">
          <svg
            viewBox={`0 0 ${VB_W} ${VB_H}`}
            preserveAspectRatio="none"
            className="block aspect-video w-full cursor-crosshair"
            role="img"
            aria-label={`Camera snapshot with ${zones.length} zones. Click to add a point; the point list beside it does the same with the keyboard.`}
            onClick={handleClick}
          >
            {src ? <image href={src} width={VB_W} height={VB_H} preserveAspectRatio="none" /> : <rect width={VB_W} height={VB_H} fill="var(--sunk)" />}
            {zones.map((z, i) => (
              <polygon
                key={i}
                points={polyPoints(z.points)}
                fill={z.kind === "privacy" ? "#000" : "var(--brand)"}
                fillOpacity={z.kind === "privacy" ? 0.55 : 0.2}
                stroke={z.kind === "privacy" ? "#fff" : "var(--brand)"}
                strokeWidth={2}
                strokeDasharray={z.kind === "privacy" ? "8 5" : undefined}
              />
            ))}
            {draft.length > 0 && (
              <polyline points={polyPoints(draft)} fill="none" stroke="#fff" strokeWidth={2} strokeDasharray="4 3" />
            )}
            {draft.map(([x, y], i) => (
              <circle key={i} cx={x * VB_W} cy={y * VB_H} r={6} fill="var(--brand)" stroke="#fff" strokeWidth={2} />
            ))}
          </svg>
        </div>
        <p className="text-[12px] text-ink-3">
          Solid outline: work zone (analysed). Dashed dark area: privacy mask (always blurred, never analysed).
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-[13px] font-medium">Zone type</legend>
          {(["work", "privacy"] as const).map((k) => (
            <label key={k} className="flex min-h-11 cursor-pointer items-center gap-2 text-[14px]">
              <input type="radio" name="zone-kind" checked={kind === k} onChange={() => setKind(k)} className="size-4 accent-[var(--brand)]" />
              {k === "work" ? "Work zone" : "Privacy mask"}
            </label>
          ))}
        </fieldset>
        {kind === "work" && (
          <Field label="Station for this work zone">
            {(id) => (
              <select id={id} className="field" value={stationId ?? ""} onChange={(e) => setStationId(Number(e.target.value))}>
                {stations.map((s) => <option key={s.id} value={s.id}>{s.code}</option>)}
              </select>
            )}
          </Field>
        )}

        <div className="flex flex-col gap-2">
          <span className="text-[13px] font-medium">Add a point by position</span>
          <div className="flex items-end gap-2">
            <Field label="Across (%)">{(id) => <input id={id} className="field w-20" type="number" min={0} max={100} value={typed.x} onChange={(e) => setTyped({ ...typed, x: e.target.value })} />}</Field>
            <Field label="Down (%)">{(id) => <input id={id} className="field w-20" type="number" min={0} max={100} value={typed.y} onChange={(e) => setTyped({ ...typed, y: e.target.value })} />}</Field>
            <button type="button" className="btn btn-ghost" onClick={addTyped}>Add point</button>
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-[13px] font-medium" id="draft-h">Points in this zone ({draft.length})</span>
          {draft.length === 0 ? (
            <p className="text-[13px] text-ink-3">No points yet. Add at least 3.</p>
          ) : (
            <ol aria-labelledby="draft-h" className="flex flex-col">
              {draft.map(([x, y], i) => (
                <li key={i} className="flex items-center justify-between gap-2 text-[13px]">
                  <span className="font-mono">{i + 1}. {pctText(x)} across, {pctText(y)} down</span>
                  <button type="button" className="btn btn-ghost min-h-11" aria-label={`Delete point ${i + 1}`} onClick={() => setDraft(draft.filter((_, j) => j !== i))}>
                    Delete
                  </button>
                </li>
              ))}
            </ol>
          )}
          <div className="mt-1 flex flex-wrap gap-2">
            <button type="button" className="btn btn-ghost" disabled={draft.length === 0} onClick={() => setDraft(draft.slice(0, -1))}>Undo</button>
            <button type="button" className="btn btn-ghost" disabled={draft.length === 0} onClick={() => setDraft([])}>Clear</button>
            <button type="button" className="btn btn-brand" disabled={!canClose} onClick={closePolygon}>Close polygon</button>
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-[13px] font-medium" id="zones-h">Saved zones ({zones.length})</span>
          {zones.length === 0 ? (
            <p className="text-[13px] text-ink-3">None yet. Draw a work zone around each station&apos;s needle and hands.</p>
          ) : (
            <ul aria-labelledby="zones-h">
              {zones.map((z, i) => (
                <li key={i} className="flex items-center justify-between gap-2 text-[13px]">
                  <span>{zoneLabel(z)} · {z.points.length} points</span>
                  <button type="button" className="btn btn-ghost min-h-11" aria-label={`Remove ${zoneLabel(z)}`} onClick={() => onChange(zones.filter((_, j) => j !== i))}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
