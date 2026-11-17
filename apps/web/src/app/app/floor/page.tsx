"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { useApi, useLiveStream, useThrottled } from "@/lib/hooks";
import type { Floor, FloorStation, OrgTree, Timeline } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { ErrorBox, Legend, LiveDot, Loading, PageHeader, STATE_META, fmtTime, minutesSince, num, pct } from "@/components/app/ui";
import { ReviewList } from "@/components/app/ReviewList";

const LANE: Record<string, string> = {
  working: "bg-run", idle: "bg-idle/70", phone_use: "bg-idle", away: "bg-off/60", break: "bg-line-2", uncertain: "bg-off/30",
  running: "bg-brand", stopped: "bg-down/80",
};

function Tile({ s, selected, onPick }: { s: FloorStation; selected: boolean; onPick: () => void }) {
  const { t } = useI18n();
  const meta = STATE_META[s.state];
  const mark = s.pending_reviews ? "▲" : meta.mark;
  return (
    <button
      type="button"
      onClick={onPick}
      aria-pressed={selected}
      aria-label={`${s.code}, ${s.worker?.name ?? "unassigned"}, ${t(meta.key)}${s.pending_reviews ? `, ${s.pending_reviews} to review` : ""}`}
      className={`flex min-h-[78px] flex-col justify-between rounded-xl border-[1.5px] p-2 text-left transition-[transform,box-shadow] duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[0_10px_24px_-14px_rgb(20_22_25/0.45)] ${meta.tile} ${
        selected ? "ring-2 ring-brand ring-offset-2 ring-offset-surface" : ""
      }`}
    >
      <span className="flex w-full items-center justify-between font-mono text-[12px] font-medium">
        {s.code.split("-").pop()}
        <span className="text-[11px]" aria-hidden="true">{mark}</span>
      </span>
      <span className="truncate text-[12px] font-medium">{s.worker?.name ?? "—"}</span>
      <span className="font-mono text-[11px] opacity-80">{num(s.output)}/{num(s.target)}</span>
    </button>
  );
}

function TimelinePanel({ stationId }: { stationId: number }) {
  const { data, error } = useApi<Timeline>(`/stations/${stationId}/timeline`, 20000);
  if (error) return <ErrorBox message={error.message} />;
  if (!data) return <div className="h-40 animate-pulse rounded-2xl bg-sunk" />;
  const start = new Date(data.shift.start).getTime(), end = new Date(data.shift.end).getTime(), span = end - start;
  const lane = (segs: Timeline["lanes"]["worker_state"]) =>
    segs.map((s) => {
      const a = new Date(s.start).getTime(), b = s.end ? new Date(s.end).getTime() : Date.now();
      return { ...s, left: ((a - start) / span) * 100, width: Math.max(0.15, ((b - a) / span) * 100) };
    });
  const hours: string[] = [];
  for (let t = start; t < end; t += 3_600_000) hours.push(new Date(t).toLocaleTimeString([], { hour: "2-digit" }));
  return (
    <section aria-labelledby="tl-h" className="panel p-5">
      <div className="mb-4 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 id="tl-h" className="text-[15px] font-semibold">{data.station.code} · {data.worker?.name ?? "Unassigned"}</h2>
        <span className="text-[13px] text-ink-3">{data.operation?.name} · SMV {data.operation?.smv} · output {num(data.output)} · efficiency {pct(data.efficiency_pct)}</span>
      </div>
      <div className="grid grid-cols-[72px_minmax(0,1fr)] items-center gap-x-3 gap-y-2">
        {(["worker_state", "machine_state"] as const).map((k) => (
          <div key={k} className="contents">
            <span className="text-[12px] text-ink-3">{k === "worker_state" ? "Worker" : "Machine"}</span>
            <div role="img" aria-label={`${k === "worker_state" ? "Worker" : "Machine"} timeline`} className="relative h-7 overflow-hidden rounded-md bg-sunk">
              {lane(data.lanes[k]).map((s) => (
                <span key={s.event_id} title={`${s.state} · ${fmtTime(s.start)}`} className={`absolute inset-y-0 ${LANE[s.state] ?? "bg-off/40"} ${s.review_status === "pending" ? "opacity-60 [background-image:repeating-linear-gradient(135deg,transparent_0_3px,rgb(255_255_255/0.6)_3px_5px)]" : ""}`} style={{ left: `${s.left}%`, width: `${s.width}%` }} />
              ))}
            </div>
          </div>
        ))}
        <span />
        <div className="grid font-mono text-[10px] text-ink-3" style={{ gridTemplateColumns: `repeat(${hours.length}, minmax(0, 1fr))` }}>
          {hours.map((h, i) => <span key={i} className="border-l border-line-2 pl-1">{h}</span>)}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-t border-line pt-3 text-[13px]">
        {Object.entries(data.minutes).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
          <span key={k} className="flex items-center gap-2"><span className={`size-2.5 rounded-[3px] ${LANE[k] ?? "bg-off"}`} /><span className="text-ink-3">{k.replace("_", " ")}</span><span className="font-mono tabular">{Math.round(v)} min</span></span>
        ))}
      </div>
    </section>
  );
}

function FloorView() {
  const { t } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const tree = useApi<OrgTree>("/org/tree");
  const lines = useMemo(() => tree.data?.flatMap((f) => f.floors.flatMap((fl) => fl.lines)) ?? [], [tree.data]);
  const lineId = Number(params.get("line")) || lines[2]?.id || lines[0]?.id;
  const floor = useApi<Floor>(lineId ? `/floor?line_id=${lineId}` : null, 15000);
  const throttled = useThrottled(floor.refresh, 2500);
  const live = useLiveStream((k, d) => (k === "station_state" ? d.line_id === lineId : true) && throttled(), lineId);
  const [picked, setPicked] = useState<number | null>(null);

  if (tree.error) return <ErrorBox message={tree.error.message} onRetry={tree.refresh} />;
  if (!lineId || (floor.loading && !floor.data)) return <Loading />;
  const f = floor.data;
  const selected = (picked && f?.stations.some((x) => x.id === picked) ? picked : null) ?? f?.stations[0]?.id ?? null;
  return (
    <>
      <PageHeader
        title={f ? `${f.line.name} · ${t("liveFloor")}` : t("liveFloor")}
        sub={f && <>{f.stations[0]?.operation?.name} · SMV {f.stations[0]?.operation?.smv} · {t("updated")} {fmtTime(f.as_of)}</>}
        actions={<LiveDot on={live} />}
      />
      <div role="tablist" aria-label="Lines" className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
        {lines.map((l) => (
          <button
            key={l.id}
            role="tab"
            type="button"
            aria-selected={l.id === lineId}
            onClick={() => { setPicked(null); router.replace(`/app/floor?line=${l.id}`); }}
            className={`-mb-px min-h-11 shrink-0 border-b-2 px-4 text-[14px] transition-colors ${l.id === lineId ? "border-brand font-semibold text-ink" : "border-transparent text-ink-3 hover:text-ink"}`}
          >
            {l.name}
          </button>
        ))}
      </div>
      {floor.error && <ErrorBox message={floor.error.message} onRetry={floor.refresh} />}
      {f && (
        <div className="flex flex-col gap-5">
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
            <section aria-labelledby="map-h" className="panel min-w-0 p-5">
              <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2">
                <h2 id="map-h" className="text-[15px] font-semibold">{f.stations.length} {t("stations")}</h2>
                <Legend />
              </div>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8">
                {f.stations.map((s) => <Tile key={s.id} s={s} selected={s.id === selected} onPick={() => setPicked(s.id)} />)}
              </div>
              {selected && (() => {
                const s = f.stations.find((x) => x.id === selected);
                return s ? <p className="mt-4 text-[13px] text-ink-3">{s.code} · {s.worker_state ?? "no state"} for {minutesSince(s.since)}</p> : null;
              })()}
            </section>
            <ReviewList lineId={lineId} compact />
          </div>
          {selected && <TimelinePanel key={selected} stationId={selected} />}
        </div>
      )}
    </>
  );
}

export default function FloorPage() {
  return (
    <Suspense fallback={<Loading />}>
      <FloorView />
    </Suspense>
  );
}
