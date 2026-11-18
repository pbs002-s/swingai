"use client";

import { useState } from "react";
import { hasRole, useMe } from "@/components/app/Shell";
import { ErrorBox, Loading, PageHeader } from "@/components/app/ui";
import { ExplainPanel } from "@/components/performance/ExplainPanel";
import { RankingTable } from "@/components/performance/RankingTable";
import { WeightsForm } from "@/components/performance/WeightsForm";
import { useApi } from "@/lib/hooks";
import { T } from "@/lib/i18n";
import type { Ranking } from "@/lib/types-performance";

const PERIODS = [7, 14, 30];

export default function PerformancePage() {
  const me = useMe();
  const [days, setDays] = useState(7);
  const [group, setGroup] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const { data, error, loading, refresh } = useApi<Ranking>(`/performance?days=${days}${group ? `&group=${encodeURIComponent(group)}` : ""}`);
  const p = data?.policy;

  return (
    <>
      <PageHeader
        title="Performance"
        sub={
          p
            ? `Ranking policy v${p.version} · production ${p.weights.production} · quality ${p.weights.quality} · productive time ${p.weights.time} · minimum coverage ${p.min_coverage_pct}%`
            : "Fair ranking within comparable operations"
        }
        actions={
          <>
            <label className="flex items-center gap-2 text-[13px] text-ink-2">
              <T>Period</T>
              <select className="field" value={days} onChange={(e) => setDays(Number(e.target.value))}>
                {PERIODS.map((d) => <option key={d} value={d}>Last {d} days</option>)}
              </select>
            </label>
            <label className="flex items-center gap-2 text-[13px] text-ink-2">
              <T>Compare within</T>
              <select className="field" value={group} onChange={(e) => { setGroup(e.target.value); setSelected(null); }}>
                <option value="">Each worker&apos;s difficulty group</option>
                {data?.groups.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
              </select>
            </label>
          </>
        }
      />
      <p role="note" className="mb-4 rounded-xl bg-brand-bg px-4 py-3 text-[14px] text-ink">
        <T>Bonus and training suggestions stay off until pilot data is validated</T>. Rankings are for review only.
      </p>
      {p && hasRole(me, "factory_admin") && <div className="mb-4 flex justify-end"><WeightsForm policy={p} onSaved={refresh} /></div>}
      {error && <div className="mb-4"><ErrorBox message={error.message} onRetry={refresh} /></div>}
      {loading && !data ? (
        <Loading />
      ) : data ? (
        <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
          <RankingTable rows={data.rows} selected={selected} onSelect={setSelected} />
          <ExplainPanel workerId={selected} days={days} group={group} />
        </div>
      ) : null}
    </>
  );
}
