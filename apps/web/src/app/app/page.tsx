"use client";

import Link from "next/link";
import { useApi, useLiveStream, useThrottled } from "@/lib/hooks";
import type { Alert, Overview, TileState } from "@/lib/api";
import { post } from "@/lib/api";
import { useI18n, T } from "@/lib/i18n";
import { ErrorBox, Legend, LiveDot, Loading, PageHeader, SeverityMark, fmtTime, num, pct } from "@/components/app/ui";

const ORDER: TileState[] = ["running", "idle", "down", "break", "no_data"];
const SEG: Record<TileState, string> = { running: "bg-run", idle: "bg-idle/70", down: "bg-down", break: "bg-line-2", no_data: "bg-off/40" };

function Summary({ o }: { o: Overview }) {
  const { t } = useI18n();
  const s = o.totals;
  const share = s.target ? Math.min(100, (s.output / s.target) * 100) : 0;
  const cells = [
    { label: t("output"), value: num(s.output), unit: `/ ${num(s.target)}`, bar: share, tone: "bg-brand", note: `${share.toFixed(0)}% of target so far` },
    { label: t("efficiency"), value: s.efficiency_pct?.toFixed(1) ?? "—", unit: "%", bar: s.efficiency_pct ?? 0, tone: "bg-brand", note: `Target ${s.target_efficiency_pct}%` },
    { label: "Stations running", value: String(s.states.running ?? 0), unit: `/ ${s.stations}`, bar: ((s.states.running ?? 0) / Math.max(1, s.stations)) * 100, tone: "bg-run", note: `${s.states.idle ?? 0} idle · ${s.states.down ?? 0} down · ${s.states.no_data ?? 0} no data` },
    { label: t("openAlerts"), value: String(s.open_alerts.critical + s.open_alerts.warning + s.open_alerts.info), unit: "", bar: 0, tone: "", note: `${s.open_alerts.critical} critical · ${s.open_alerts.warning} warning` },
  ];
  return (
    <section aria-label="Shift summary" className="panel grid grid-cols-2 lg:grid-cols-4">
      {cells.map((c, i) => (
        <div key={c.label} className={`flex flex-col gap-1.5 p-5 ${i % 2 ? "" : "border-r border-line"} ${i < 2 ? "border-b border-line lg:border-b-0" : ""} lg:border-r lg:last:border-r-0`}>
          <span className="text-[13px] text-ink-3">{c.label}</span>
          <span className="flex items-baseline gap-1.5">
            <span className="font-mono text-[28px] font-medium tracking-[-0.03em] tabular">{c.value}</span>
            <span className="font-mono text-[14px] text-ink-3">{c.unit}</span>
          </span>
          {c.tone && <span className="h-1 overflow-hidden rounded-full bg-sunk"><span className={`block h-full rounded-full ${c.tone} transition-[width] duration-700 ease-out`} style={{ width: `${c.bar}%` }} /></span>}
          <span className="text-[12px] text-ink-3">{c.note}</span>
        </div>
      ))}
    </section>
  );
}

function Lines({ o }: { o: Overview }) {
  return (
    <section aria-labelledby="lines-h" className="panel min-w-0 overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3.5">
        <h2 id="lines-h" className="text-[15px] font-semibold"><T>Lines</T></h2>
        <Legend />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-[14px]">
          <thead>
            <tr className="text-left text-[12px] text-ink-3">
              <th className="px-5 py-2.5 font-medium"><T>Line</T></th>
              <th className="px-2 py-2.5 font-medium"><T>Stations</T></th>
              <th className="px-2 py-2.5 text-right font-medium"><T>Output / target</T></th>
              <th className="px-2 py-2.5 text-right font-medium"><T>Efficiency</T></th>
              <th className="px-5 py-2.5 font-medium"><T>Alerts</T></th>
            </tr>
          </thead>
          <tbody>
            {o.lines.map((l) => {
              const total = Math.max(1, ORDER.reduce((a, k) => a + (l.states[k] ?? 0), 0));
              const alerts = l.open_alerts.critical + l.open_alerts.warning + l.open_alerts.info;
              return (
                <tr key={l.id} className="border-t border-line transition-colors hover:bg-bg">
                  <td className="px-5 py-3">
                    <Link href={`/app/floor?line=${l.id}`} className="flex flex-col">
                      <span className="font-medium">{l.name}</span>
                      <span className="text-[12px] text-ink-3">{l.operation}</span>
                    </Link>
                  </td>
                  <td className="min-w-[200px] px-2 py-3">
                    <span className="flex h-2 gap-[2px] overflow-hidden rounded-full">
                      {ORDER.map((k) => (l.states[k] ? <span key={k} className={SEG[k]} style={{ flex: `${l.states[k]} 0 0` }} /> : null))}
                    </span>
                    <span className="font-mono text-[11px] text-ink-3">{l.states.running ?? 0} run · {l.states.idle ?? 0} idle · {l.states.down ?? 0} down · {total} total</span>
                  </td>
                  <td className="px-2 py-3 text-right font-mono tabular">{num(l.output)} / {num(l.target)}</td>
                  <td className="px-2 py-3 text-right font-mono tabular">{pct(l.efficiency_pct)}</td>
                  <td className="px-5 py-3">
                    {alerts ? (
                      <span className={`rounded-md px-2 py-0.5 text-[12px] font-medium ${l.open_alerts.critical ? "bg-down-bg text-down" : "bg-idle-bg text-idle"}`}>{alerts} open</span>
                    ) : (
                      <span className="text-[12px] text-ink-3"><T>None</T></span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AlertFeed() {
  const { t } = useI18n();
  const { data, refresh } = useApi<Alert[]>("/alerts?limit=6", 20000);
  const throttled = useThrottled(refresh, 1500);
  useLiveStream((k) => (k === "alert" || k === "alert_update") && throttled());
  async function ack(id: number) {
    await post(`/alerts/${id}/ack`);
    void refresh();
  }
  return (
    <section aria-labelledby="alerts-h" className="panel min-w-0 overflow-hidden">
      <div className="flex items-center border-b border-line px-5 py-3.5">
        <h2 id="alerts-h" className="text-[15px] font-semibold"><T>Alert center</T></h2>
        <Link href="/app/alerts" className="link-draw ml-auto text-[13px] text-brand"><T>All alerts</T></Link>
      </div>
      <ul>
        {(data ?? []).map((a) => (
          <li key={a.id} className="flex items-start gap-3 border-b border-line px-5 py-3 last:border-b-0">
            <SeverityMark level={a.severity} />
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="truncate text-[14px] font-medium">{a.title}</span>
              <span className="truncate font-mono text-[12px] text-ink-3">{a.line?.name ?? "Factory"} · {a.detail}</span>
            </span>
            {a.status === "open" ? (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => ack(a.id)}>{t("acknowledge")}</button>
            ) : (
              <span className="pt-1 text-[12px] text-ink-3"><T>Acknowledged</T></span>
            )}
          </li>
        ))}
        {data && data.length === 0 && <li className="px-5 py-10 text-center text-[14px] text-ink-3"><T>No open alerts. The floor is quiet.</T></li>}
      </ul>
    </section>
  );
}

function Hourly({ o }: { o: Overview }) {
  const perHour = o.totals.target / Math.max(1, o.hourly.filter((h) => !h.is_break).length);
  const max = Math.max(perHour * 1.15, ...o.hourly.map((h) => h.output), 1);
  return (
    <section aria-labelledby="hourly-h" className="panel min-w-0 p-5">
      <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-1">
        <h2 id="hourly-h" className="text-[15px] font-semibold"><T>Output by hour</T></h2>
        <span className="flex items-center gap-1.5 text-[12px] text-ink-3"><span className="size-2.5 rounded-[3px] bg-brand" /><T>Confirmed units</T></span>
        <span className="flex items-center gap-1.5 text-[12px] text-ink-3"><span className="w-4 border-t-2 border-dashed border-ink" /><T>Target pace</T></span>
      </div>
      <div role="img" aria-label={`Output by hour: ${o.hourly.map((h) => `${h.hour} ${h.output}`).join(", ")}`} className="relative grid h-[200px] items-end gap-2" style={{ gridTemplateColumns: `repeat(${o.hourly.length}, minmax(0, 1fr))` }}>
        <div aria-hidden="true" className="absolute inset-x-0 border-t-2 border-dashed border-ink/50" style={{ bottom: `${(perHour / max) * 100}%` }} />
        {o.hourly.map((h) => (
          <div key={h.hour} className="flex h-full flex-col items-center justify-end gap-1">
            {h.output > 0 && <span className="font-mono text-[10px] text-ink-3">{num(h.output)}</span>}
            <div className={`w-full max-w-[40px] rounded-t-md transition-[height] duration-700 ease-out ${h.is_break ? "bg-line" : "bg-brand"}`} style={{ height: `${(h.output / max) * 100}%` }} />
          </div>
        ))}
      </div>
      <div className="mt-2 grid gap-2" style={{ gridTemplateColumns: `repeat(${o.hourly.length}, minmax(0, 1fr))` }}>
        {o.hourly.map((h) => <span key={h.hour} className="text-center font-mono text-[11px] text-ink-3">{h.is_break ? "break" : h.hour.slice(0, 2)}</span>)}
      </div>
    </section>
  );
}

function Devices({ o }: { o: Overview }) {
  const names: Record<string, string> = { camera: "Cameras", machine_sensor: "Machine sensors", edge_box: "Edge boxes", card_reader: "Card readers" };
  return (
    <section aria-labelledby="dev-h" className="panel p-5">
      <h2 id="dev-h" className="mb-2 text-[15px] font-semibold"><T>Devices</T></h2>
      {o.devices.map((d) => {
        const off = d.total - d.online;
        return (
          <div key={d.kind} className="flex items-center gap-3 border-t border-line py-2.5 first-of-type:border-t-0">
            <span className="flex-1 text-[14px]">{names[d.kind] ?? d.kind}</span>
            <span className="font-mono text-[13px] tabular">{d.online} / {d.total}</span>
            <span className={`rounded-md px-2 py-0.5 text-[12px] font-medium ${off ? "bg-idle-bg text-idle" : "bg-run-bg text-run"}`}>{off ? `${off} offline` : "OK"}</span>
          </div>
        );
      })}
    </section>
  );
}

export default function OverviewPage() {
  const { t } = useI18n();
  const { data, error, loading, refresh } = useApi<Overview>("/overview", 15000);
  const throttled = useThrottled(refresh, 4000);
  const live = useLiveStream((k) => k === "station_state" && throttled());

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox message={error.message} onRetry={refresh} />;
  if (!data) return null;
  return (
    <>
      <PageHeader
        title={t("overview")}
        sub={<>{data.factory.name} · {t("dayShift")} {fmtTime(data.shift.start)}–{fmtTime(data.shift.end)} · {t("updated")} {fmtTime(data.as_of)}</>}
        actions={<LiveDot on={live} />}
      />
      <div className="flex flex-col gap-5">
        <Summary o={data} />
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <Lines o={data} />
          <AlertFeed />
        </div>
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <Hourly o={data} />
          <Devices o={data} />
        </div>
      </div>
    </>
  );
}
