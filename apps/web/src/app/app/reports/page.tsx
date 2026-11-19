"use client";

import { useState } from "react";
import { Empty, ErrorBox, Loading, PageHeader } from "@/components/app/ui";
import { useApi } from "@/lib/hooks";
import type { OrgTree } from "@/lib/api";

type DayReport = {
  date: string;
  timezone: string;
  partial: boolean;
  line: { id: number; code: string; name: string };
  generated_at: string;
  workers: {
    worker: { id: number; name: string; code: string | null };
    operation: string;
    accepted: number;
    rework: number;
    rejected: number;
    efficiency_pct: number | null;
    first_pass_pct: number | null;
    attended_min: number;
    downtime_min: number;
    coverage_pct: number;
    state_min: Record<string, number>;
  }[];
  stations: { code: string; stops: number; down_min: number }[];
  totals: { accepted: number; rework: number; rejected: number; stops: number; down_min: number };
};

const yesterday = () => new Date(Date.now() - 86_400_000).toLocaleDateString("en-CA"); // YYYY-MM-DD in local time
const pct = (v: number | null) => (v === null ? "–" : `${v}%`);
const STATE_LABEL: Record<string, string> = { working: "Working", idle: "Idle", phone_use: "Phone use", away: "Away", uncertain: "Unsure" };

export default function ReportsPage() {
  const tree = useApi<OrgTree>("/org/tree");
  const lines = tree.data?.flatMap((f) => f.floors.flatMap((fl) => fl.lines)) ?? [];
  const [date, setDate] = useState(yesterday());
  const [lineId, setLineId] = useState<number | null>(null);
  const line = lineId ?? lines[0]?.id ?? null;
  const q = line === null ? null : `date=${date}&line_id=${line}`;
  const report = useApi<DayReport>(q ? `/reports/day?${q}` : null);
  const d = report.data;

  return (
    <>
      <div className="print:hidden">
        <PageHeader
          title="Reports"
          sub="Day report for one line. Print it to save as PDF, or download the figures as CSV."
          actions={
            <>
              <label className="flex items-center gap-2 text-[13px]">
                Line
                <select className="field" value={line ?? ""} onChange={(e) => setLineId(Number(e.target.value))}>
                  {lines.map((l) => <option key={l.id} value={l.id}>{l.code} · {l.name}</option>)}
                </select>
              </label>
              <label className="flex items-center gap-2 text-[13px]">
                Date
                <input type="date" className="field" value={date} max={new Date().toLocaleDateString("en-CA")} onChange={(e) => setDate(e.target.value)} />
              </label>
              <button className="btn btn-brand" onClick={() => window.print()} disabled={!d}>Print / save as PDF</button>
              {q && <a className="btn" href={`/api/v1/reports/day.csv?${q}`} download>Workers CSV</a>}
              {q && <a className="btn" href={`/api/v1/reports/day.csv?${q}&section=downtime`} download>Downtime CSV</a>}
            </>
          }
        />
      </div>
      {report.error && <ErrorBox message={report.error.message} onRetry={report.refresh} />}
      {report.loading && !d ? <Loading /> : !d ? (
        !report.error && <Empty title="No line selected" text="Pick a line and a date." />
      ) : (
        <article aria-label="Day report" className="panel grid gap-6 p-6 print:border-0 print:p-0">
          <header>
            <h2 className="text-[22px] font-semibold">{d.line.name} ({d.line.code}) · {d.date}</h2>
            <p className="text-[13px] text-ink-3">
              Times in {d.timezone}. {d.partial && "This day is not finished: figures run up to the time shown below. "}
              Generated {new Date(d.generated_at).toLocaleString()}.
            </p>
          </header>

          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {[
              ["Accepted pieces", d.totals.accepted],
              ["Rework", d.totals.rework],
              ["Rejected", d.totals.rejected],
              ["Machine stops", d.totals.stops],
              ["Downtime (min)", d.totals.down_min],
            ].map(([k, v]) => (
              <div key={k} className="rounded-lg border border-line p-3">
                <dt className="text-[12px] text-ink-3">{k}</dt>
                <dd className="font-mono text-[20px]">{v}</dd>
              </div>
            ))}
          </dl>

          <section aria-labelledby="w-h">
            <h3 id="w-h" className="mb-2 text-[16px] font-semibold">Workers</h3>
            {d.workers.length === 0 ? (
              <p className="text-[14px] text-ink-3">No production was entered for this line on this day.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[13px]">
                  <thead className="border-b border-line text-[12px] text-ink-3">
                    <tr>
                      {["Worker", "Operation", "Accepted", "Rework", "Rejected", "Efficiency", "First pass", "Attended min", "Coverage", ...Object.values(STATE_LABEL).map((s) => `${s} min`)].map((h) => (
                        <th key={h} scope="col" className="px-2 py-2 font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {d.workers.map((w) => (
                      <tr key={w.worker.id} className="border-t border-line">
                        <th scope="row" className="px-2 py-2 font-medium">{w.worker.name}{w.worker.code ? ` (${w.worker.code})` : ""}</th>
                        <td className="px-2 py-2">{w.operation}</td>
                        <td className="px-2 py-2 font-mono">{w.accepted}</td>
                        <td className="px-2 py-2 font-mono">{w.rework}</td>
                        <td className="px-2 py-2 font-mono">{w.rejected}</td>
                        <td className="px-2 py-2 font-mono">{pct(w.efficiency_pct)}</td>
                        <td className="px-2 py-2 font-mono">{pct(w.first_pass_pct)}</td>
                        <td className="px-2 py-2 font-mono">{w.attended_min}</td>
                        <td className="px-2 py-2 font-mono">{pct(w.coverage_pct)}</td>
                        {Object.keys(STATE_LABEL).map((s) => <td key={s} className="px-2 py-2 font-mono">{w.state_min[s] ?? 0}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section aria-labelledby="d-h">
            <h3 id="d-h" className="mb-2 text-[16px] font-semibold">Machine downtime</h3>
            {d.stations.length === 0 ? (
              <p className="text-[14px] text-ink-3">No machine stops longer than the downtime threshold.</p>
            ) : (
              <table className="w-full max-w-md text-left text-[13px]">
                <thead className="border-b border-line text-[12px] text-ink-3">
                  <tr><th scope="col" className="px-2 py-2 font-medium">Station</th><th scope="col" className="px-2 py-2 font-medium">Stops</th><th scope="col" className="px-2 py-2 font-medium">Minutes</th></tr>
                </thead>
                <tbody>
                  {d.stations.map((s) => (
                    <tr key={s.code} className="border-t border-line"><th scope="row" className="px-2 py-2 font-medium">{s.code}</th><td className="px-2 py-2 font-mono">{s.stops}</td><td className="px-2 py-2 font-mono">{s.down_min}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
          <p className="text-[12px] text-ink-3">
            Detected activity (idle, away, phone use) is a camera estimate, not a confirmed fact. Nothing here is a decision about a person.
          </p>
        </article>
      )}
    </>
  );
}
