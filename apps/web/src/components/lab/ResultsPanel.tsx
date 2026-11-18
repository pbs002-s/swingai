"use client";

import { STATES } from "@/components/lab/activity";
import type { ActivityState, Tracker } from "@/components/lab/activity";

const LABEL: Record<ActivityState, string> = {
  working: "Working",
  idle: "Idle",
  phone_use: "Phone use (needs review)",
  away: "Away from camera",
  uncertain: "Not sure yet",
};
const TONE: Record<ActivityState, string> = {
  working: "bg-run-bg text-run",
  idle: "bg-idle-bg text-idle",
  phone_use: "bg-down-bg text-down",
  away: "bg-sunk text-ink-2",
  uncertain: "bg-off-bg text-ink-2",
};

export const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

type Props = { tracker: Tracker | null; status: string };

export function ResultsPanel({ tracker, status }: Props) {
  if (!tracker) {
    return <p className="text-[14px] text-ink-3" role="status">{status}</p>;
  }
  const elapsed = tracker.lastT - tracker.startedAt;
  const recent = tracker.changes.slice(-8).reverse();
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-[13px] text-ink-3">Right now</span>
        <span aria-live="polite" className={`rounded-lg px-3 py-1 text-[15px] font-medium ${TONE[tracker.state]}`}>
          {LABEL[tracker.state]}
        </span>
        <span className="text-[13px] text-ink-3">Session {clock(elapsed)}</span>
      </div>

      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <div className="rounded-lg border border-line p-3">
          <dt className="text-[12px] text-ink-3">In front of camera</dt>
          <dd className="font-mono text-[20px]">{clock(tracker.inViewS)}</dd>
        </div>
        {STATES.map((s) => (
          <div key={s} className="rounded-lg border border-line p-3">
            <dt className="text-[12px] text-ink-3">{LABEL[s]}</dt>
            <dd className="font-mono text-[20px]">{clock(tracker.totals[s])}</dd>
          </div>
        ))}
      </dl>

      <section aria-labelledby="phone-h" className="grid gap-1">
        <h3 id="phone-h" className="text-[14px] font-medium">Phone use detected ({tracker.phoneEvents.length})</h3>
        {tracker.phoneEvents.length === 0 ? (
          <p className="text-[13px] text-ink-3">None so far.</p>
        ) : (
          <ul className="text-[13px]">
            {tracker.phoneEvents.slice(-5).reverse().map((e) => (
              <li key={e.t}>At {clock(e.t - tracker.startedAt)}, confidence {Math.round(e.confidence * 100)}%. A supervisor would review this; it is not a confirmed fact.</li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="tl-h" className="grid gap-1">
        <h3 id="tl-h" className="text-[14px] font-medium">Timeline</h3>
        {recent.length === 0 ? (
          <p className="text-[13px] text-ink-3">No changes yet.</p>
        ) : (
          <ol className="font-mono text-[13px]">
            {recent.map((c) => (
              <li key={c.t}>{clock(c.t - tracker.startedAt)} {LABEL[c.from]} → {LABEL[c.to]}</li>
            ))}
          </ol>
        )}
      </section>

      <p className="rounded-lg border border-line bg-sunk px-3 py-2 text-[13px] text-ink-2">
        Needle breaks are not detected from video. A webcam cannot see them reliably; they come from sensors or manual entry.
      </p>
    </div>
  );
}
