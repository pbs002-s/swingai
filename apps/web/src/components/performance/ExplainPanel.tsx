"use client";

import { ErrorBox } from "@/components/app/ui";
import { useApi } from "@/lib/hooks";
import { T } from "@/lib/i18n";
import type { Explanation } from "@/lib/types-performance";

export function ExplainPanel({ workerId, days, group }: { workerId: number | null; days: number; group: string }) {
  const path = workerId == null ? null : `/performance/workers/${workerId}?days=${days}${group ? `&group=${encodeURIComponent(group)}` : ""}`;
  const { data, error, loading, refresh } = useApi<Explanation>(path);

  return (
    <section role="region" aria-labelledby="why-h" aria-live="polite" className="panel flex min-w-0 flex-col gap-3.5 p-5">
      {workerId == null ? (
        <>
          <h2 id="why-h" className="text-[15px] font-semibold"><T>Score explanation</T></h2>
          <p className="text-[14px] text-ink-3"><T>Pick a worker to see how each part of the score was calculated.</T></p>
        </>
      ) : error ? (
        <>
          <h2 id="why-h" className="text-[15px] font-semibold"><T>Score explanation</T></h2>
          <ErrorBox message={error.message} onRetry={refresh} />
        </>
      ) : loading || !data || data.worker.id !== workerId ? (
        <>
          <h2 id="why-h" className="text-[15px] font-semibold"><T>Score explanation</T></h2>
          <div role="status" className="h-40 animate-pulse rounded-xl bg-sunk"><span className="sr-only">Loading</span></div>
        </>
      ) : (
        <Body data={data} />
      )}
    </section>
  );
}

function Body({ data }: { data: Explanation }) {
  const ex = data.excluded;
  const rejected = Object.entries(ex.rejected_min).filter(([, v]) => v > 0);
  return (
    <>
      <h2 id="why-h" className="text-[15px] font-semibold">
        {data.eligible ? `Why ${data.worker.name} scores ${data.total?.toFixed(1)}` : `${data.worker.name}: insufficient data`}
      </h2>
      {!data.eligible && (
        <p className="text-[13px] leading-[1.5] text-ink-2">
          Coverage is {Math.round(data.coverage_pct)}%, below the policy minimum. No score or rank is given; the figures below are for checking the records.
        </p>
      )}
      {data.components.map((c) => (
        <div key={c.key} className="flex flex-col gap-1.5 border-t border-line pt-2.5">
          <span className="flex items-baseline gap-3">
            <span className="font-medium">
              {c.label} {c.weight}%
            </span>
            <span className="ml-auto font-mono text-[13px] tabular">
              {c.score == null ? "—" : `${c.score.toFixed(1)} × ${(c.weight / 100).toFixed(2)} = ${c.contribution?.toFixed(1)}`}
            </span>
          </span>
          <span className="text-[13px] text-ink-3">
            {c.value == null ? "—" : `${c.value.toFixed(1)}`} {c.unit}
          </span>
          <span className="text-[13px] leading-[1.5] text-ink-2">{c.source}</span>
        </div>
      ))}
      <p className="border-t border-line pt-2.5 text-[13px] leading-[1.5] text-ink-2">
        Excluded: {ex.downtime_min} min machine downtime
        {rejected.length > 0 && <>, {rejected.map(([k, v]) => `${v} min ${k.replace("_", " ")}`).join(", ")} rejected on review</>}. Scheduled{" "}
        {ex.scheduled_min} min on attended shift days. Policy version {data.policy_version_id ?? "default"}.
      </p>
    </>
  );
}
