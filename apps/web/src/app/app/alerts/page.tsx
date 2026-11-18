"use client";

import { useState } from "react";
import { ApiFailure, post } from "@/lib/api";
import type { Alert } from "@/lib/api";
import { useApi, useLiveStream, useThrottled } from "@/lib/hooks";
import { T, useI18n } from "@/lib/i18n";
import { Empty, ErrorBox, LiveDot, Loading, PageHeader, SeverityMark, fmtTime } from "@/components/app/ui";

const FILTERS = [
  { key: "", label: "All" },
  { key: "critical", label: "Critical" },
  { key: "warning", label: "Warning" },
  { key: "info", label: "Info" },
] as const;

export default function AlertsPage() {
  const { t } = useI18n();
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState<"active" | "resolved">("active");
  const { data, meta, error, loading, refresh } = useAlerts(severity, status);
  const throttled = useThrottled(refresh, 1500);
  const live = useLiveStream((k) => (k === "alert" || k === "alert_update") && throttled());
  const [failure, setFailure] = useState<string | null>(null);

  async function act(a: Alert, action: "ack" | "resolve") {
    setFailure(null);
    try {
      await post(`/alerts/${a.id}/${action}`);
      void refresh();
    } catch (e) {
      setFailure(e instanceof ApiFailure ? e.message : "Could not update the alert.");
    }
  }

  const counts = meta;
  return (
    <>
      <PageHeader title={t("alerts")} sub="Every alert from every line. Rules and thresholds are edited in Settings." actions={<LiveDot on={live} />} />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Severity" className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              aria-pressed={severity === f.key}
              onClick={() => setSeverity(f.key)}
              className={`btn btn-sm ${severity === f.key ? "btn-primary" : "btn-ghost"}`}
            >
              <T>{f.label}</T>
              {f.key && counts ? <span className="font-mono opacity-70">{counts[f.key as "critical"] ?? 0}</span> : null}
            </button>
          ))}
        </div>
        <div role="group" aria-label="Status" className="ml-auto flex overflow-hidden rounded-lg border border-line-2 text-[13px]">
          {(["active", "resolved"] as const).map((s) => (
            <button key={s} type="button" aria-pressed={status === s} onClick={() => setStatus(s)} className={`min-h-9 px-3 capitalize ${status === s ? "bg-ink text-bg" : "text-ink-2 hover:bg-sunk"}`}>
              <T>{s === "active" ? "Active" : "Resolved"}</T>
            </button>
          ))}
        </div>
      </div>
      {failure && <div className="mb-3"><ErrorBox message={failure} /></div>}
      {error && <ErrorBox message={error.message} onRetry={refresh} />}
      {loading && !data ? (
        <Loading />
      ) : (
        <section className="panel overflow-hidden" aria-label="Alerts">
          {data?.length === 0 && <Empty title="No alerts here" text="When a rule fires it shows up here and on the overview." />}
          <ul>
            {data?.map((a) => (
              <li key={a.id} className="flex flex-wrap items-start gap-3 border-b border-line px-5 py-3.5 last:border-b-0 sm:flex-nowrap">
                <SeverityMark level={a.severity} />
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-[14px] font-semibold">{a.title}</span>
                  <span className="text-[13px] text-ink-2">{a.detail}</span>
                  <span className="font-mono text-[12px] text-ink-3">
                    {a.line?.name ?? "Factory"} · {fmtTime(a.created_at)} · {a.status}
                  </span>
                </div>
                {a.status !== "resolved" && (
                  <div className="flex gap-2">
                    {a.status === "open" && <button type="button" className="btn btn-ghost btn-sm" onClick={() => act(a, "ack")}>{t("acknowledge")}</button>}
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => act(a, "resolve")}>{t("resolve")}</button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function useAlerts(severity: string, status: string) {
  const q = new URLSearchParams({ status, limit: "100" });
  if (severity) q.set("severity", severity);
  const res = useApi<Alert[]>(`/alerts?${q}`, 20000);
  return { ...res, meta: undefined as Record<string, number> | undefined };
}
