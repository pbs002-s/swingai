"use client";

import { useState } from "react";
import { ApiFailure, post } from "@/lib/api";
import type { NeedleLot } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { hasRole, useMe } from "@/components/app/Shell";
import { ErrorBox, Loading, PageHeader } from "@/components/app/ui";

const PATTERN: Record<NeedleLot["pattern"], { label: string; cls: string; bar: string }> = {
  batch: { label: "Batch pattern", cls: "bg-down-bg text-down", bar: "bg-down" },
  machine: { label: "One machine", cls: "bg-idle-bg text-idle", bar: "bg-idle" },
  worker: { label: "One worker", cls: "bg-idle-bg text-idle", bar: "bg-idle" },
  normal: { label: "Normal", cls: "bg-run-bg text-run", bar: "bg-brand" },
  too_little_use: { label: "Too little use", cls: "bg-off-bg text-ink-2", bar: "bg-off/60" },
};
const ALERT_AT = 25;

export default function NeedlesPage() {
  const me = useMe();
  const { data, error, loading, refresh } = useApi<NeedleLot[]>("/needles/stats");
  const [failure, setFailure] = useState<string | null>(null);
  const canQuarantine = hasRole(me, "factory_admin", "quality", "maintenance");
  const max = Math.max(ALERT_AT * 2, ...(data ?? []).map((l) => l.breaks_per_1000h));
  const worst = data?.find((l) => l.pattern === "batch");

  async function quarantine(lot: NeedleLot) {
    setFailure(null);
    try {
      await post(`/needle-batches/${lot.batch_id}/quarantine`);
      void refresh();
    } catch (e) {
      setFailure(e instanceof ApiFailure ? e.message : "Could not quarantine the lot.");
    }
  }

  if (loading && !data) return <Loading />;
  return (
    <>
      <PageHeader title="Needles" sub="Confirmed breaks only. A lot is judged after at least 10 needles and 50 running hours." />
      {error && <ErrorBox message={error.message} onRetry={refresh} />}
      {failure && <div className="mb-3"><ErrorBox message={failure} /></div>}
      {data && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
          <section aria-labelledby="lots-h" className="panel min-w-0 overflow-hidden">
            <div className="flex items-center border-b border-line px-5 py-3.5">
              <h2 id="lots-h" className="text-[15px] font-semibold">Lots by breaks per 1,000 running hours</h2>
              <span className="ml-auto text-[12px] text-ink-3">alert at {ALERT_AT}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-[14px]">
                <thead>
                  <tr className="text-left text-[12px] text-ink-3">
                    <th className="px-5 py-2.5 font-medium">Lot</th>
                    <th className="px-2 py-2.5 font-medium">Supplier · model</th>
                    <th className="px-2 py-2.5 text-right font-medium">Issued</th>
                    <th className="px-2 py-2.5 text-right font-medium">Breaks</th>
                    <th className="w-[30%] px-2 py-2.5 font-medium">Rate</th>
                    <th className="px-5 py-2.5 font-medium">Pattern</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((l) => (
                    <tr key={l.batch_id} className={`border-t border-line ${l.pattern === "batch" ? "bg-down-bg/40" : ""}`}>
                      <td className="px-5 py-3 font-mono font-medium">{l.lot_no}{l.status === "quarantined" && <span className="ml-2 rounded bg-ink px-1.5 py-px font-sans text-[11px] text-bg">quarantined</span>}</td>
                      <td className="px-2 py-3"><span className="flex flex-col"><span>{l.supplier}</span><span className="font-mono text-[12px] text-ink-3">{l.model}</span></span></td>
                      <td className="px-2 py-3 text-right font-mono tabular">{l.issued}</td>
                      <td className="px-2 py-3 text-right font-mono tabular">{l.confirmed_breaks}</td>
                      <td className="px-2 py-3">
                        <span className="flex items-center gap-3">
                          <span className="relative h-2.5 flex-1 rounded-full bg-sunk">
                            <span className={`absolute inset-y-0 left-0 rounded-full ${PATTERN[l.pattern].bar}`} style={{ width: `${Math.min(100, (l.breaks_per_1000h / max) * 100)}%` }} />
                            <span aria-hidden="true" className="absolute -inset-y-1 border-l-2 border-dashed border-ink" style={{ left: `${(ALERT_AT / max) * 100}%` }} />
                          </span>
                          <span className="w-12 text-right font-mono tabular">{l.breaks_per_1000h}</span>
                        </span>
                      </td>
                      <td className="px-5 py-3"><span className={`whitespace-nowrap rounded-md px-2 py-0.5 text-[12px] font-medium ${PATTERN[l.pattern].cls}`}>{PATTERN[l.pattern].label}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {worst && (
            <section aria-labelledby="inv-h" className="panel flex flex-col gap-4 p-5">
              <h2 id="inv-h" className="text-[15px] font-semibold">Lot {worst.lot_no} · investigate</h2>
              <p className="text-[14px] leading-[1.55] text-ink-2">
                Breaks spread across {worst.machines} machines and {worst.workers} workers. That points to the lot, not to one station or one person.
              </p>
              <div className="grid grid-cols-3 overflow-hidden rounded-xl border border-line">
                {[[worst.confirmed_breaks, "confirmed breaks"], [worst.machines, "machines"], [worst.workers, "workers"]].map(([v, k]) => (
                  <div key={k} className="flex flex-col gap-0.5 border-r border-line p-3 last:border-r-0">
                    <span className="font-mono text-[22px] font-medium tabular">{v}</span>
                    <span className="text-[12px] text-ink-3">{k}</span>
                  </div>
                ))}
              </div>
              {canQuarantine && worst.status !== "quarantined" ? (
                <button type="button" className="btn btn-primary self-start" onClick={() => quarantine(worst)}>Quarantine lot {worst.lot_no}</button>
              ) : (
                <p className="text-[13px] text-ink-3">{worst.status === "quarantined" ? "This lot is quarantined. No new needles can be issued from it." : "Quality or maintenance can quarantine this lot."}</p>
              )}
            </section>
          )}
        </div>
      )}
    </>
  );
}
