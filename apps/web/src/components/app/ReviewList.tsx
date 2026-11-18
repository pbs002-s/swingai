"use client";

import Link from "next/link";
import { useState } from "react";
import { ApiFailure, post } from "@/lib/api";
import type { ReviewItem } from "@/lib/api";
import { useApi, useLiveStream, useThrottled } from "@/lib/hooks";
import { useI18n, T } from "@/lib/i18n";
import { Empty, ErrorBox, fmtTime } from "./ui";

const RECLASSIFY: Record<string, { value: string; label: string }[]> = {
  worker_state: [
    { value: "working", label: "Was working" },
    { value: "idle", label: "Was idle" },
    { value: "away", label: "Was away" },
  ],
  needle_event: [
    { value: "needle_break", label: "Needle break" },
    { value: "thread_break", label: "Thread break" },
    { value: "jam", label: "Machine jam" },
  ],
};

function duration(s: number | null) {
  if (s == null) return "ongoing";
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}

export function ReviewList({ lineId, compact = false }: { lineId?: number; compact?: boolean }) {
  const { t } = useI18n();
  const path = `/events/review-queue?limit=${compact ? 4 : 50}${lineId ? `&line_id=${lineId}` : ""}`;
  const { data, error, refresh } = useApi<ReviewItem[]>(path, 20000);
  const throttled = useThrottled(refresh, 2000);
  useLiveStream((k) => (k === "review_added" || k === "review_done") && throttled(), lineId);
  const [busy, setBusy] = useState<number | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [done, setDone] = useState<Record<number, string>>({});

  async function decide(item: ReviewItem, decision: "confirm" | "reject" | "reclassify", newState?: string) {
    setBusy(item.id);
    setFailure(null);
    try {
      await post(`/events/${item.id}/review`, { decision, new_state: newState });
      setDone((d) => ({ ...d, [item.id]: decision === "reclassify" ? `Changed to ${newState?.replace("_", " ")}` : decision === "confirm" ? "Confirmed" : "Rejected" }));
      void refresh();
    } catch (e) {
      setFailure(e instanceof ApiFailure ? e.message : "Could not save the review.");
    } finally {
      setBusy(null);
    }
  }

  const items = data ?? [];
  return (
    <section aria-labelledby="queue-h" className="panel min-w-0 overflow-hidden">
      <div className="flex items-center gap-2 border-b border-line px-5 py-3.5">
        <h2 id="queue-h" className="text-[15px] font-semibold">{t("reviewQueue")}</h2>
        <span className="font-mono text-[13px] text-ink-3">{items.length}{compact && items.length === 4 ? "+" : ""}</span>
        {compact && <Link href="/app/review" className="link-draw ml-auto text-[13px] text-brand"><T>Open queue</T></Link>}
      </div>
      {error && <div className="p-4"><ErrorBox message={error.message} onRetry={refresh} /></div>}
      {failure && <div className="px-5 pt-3"><ErrorBox message={failure} /></div>}
      {data && items.length === 0 && <Empty title="Nothing to review" text="Events the system is unsure about will wait here for a person to decide." />}
      <ul>
        {items.map((item) => (
          <li key={item.id} className="flex flex-col gap-3 border-b border-line px-5 py-4 last:border-b-0">
            <div className="flex gap-3">
              <div aria-hidden="true" className="grid h-[60px] w-[78px] shrink-0 place-items-center rounded-lg border border-line-2 bg-[repeating-linear-gradient(135deg,var(--sunk)_0_6px,var(--bg)_6px_12px)] px-1 text-center text-[10px] leading-tight text-ink-3">
                {item.source === "vision" ? "still · blurred" : item.event_type === "needle_event" ? "sensor event" : "simulated"}
              </div>
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] font-semibold">{item.title}</span>
                  {item.confidence != null && (
                    <span className={`rounded px-1.5 py-px font-mono text-[11px] ${item.confidence < 0.75 ? "bg-off-bg text-ink-2" : "bg-idle-bg text-idle"}`}>{item.confidence.toFixed(2)}</span>
                  )}
                </span>
                <span className="truncate text-[13px] text-ink-2">{item.station.code} · {item.worker?.name ?? "unassigned"} · {duration(item.duration_s)}</span>
                <span className="font-mono text-[12px] text-ink-3">{fmtTime(item.start_time)} · {item.line.name}</span>
              </div>
            </div>
            {done[item.id] ? (
              <span role="status" className="text-[13px] font-medium text-run">{done[item.id]}</span>
            ) : (
              <div className="flex flex-wrap gap-2">
                <button type="button" className="btn btn-brand btn-sm min-h-10" disabled={busy === item.id} onClick={() => decide(item, "confirm")}>{t("confirm")}</button>
                <button type="button" className="btn btn-ghost btn-sm min-h-10" disabled={busy === item.id} onClick={() => decide(item, "reject")}>{t("reject")}</button>
                {(RECLASSIFY[item.event_type] ?? []).filter((o) => o.value !== item.state).slice(0, compact ? 1 : 3).map((o) => (
                  <button key={o.value} type="button" className="btn btn-ghost btn-sm min-h-10" disabled={busy === item.id} onClick={() => decide(item, "reclassify", o.value)}>{o.label}</button>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
