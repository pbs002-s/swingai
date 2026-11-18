"use client";

import { Empty, pct } from "@/components/app/ui";
import { T } from "@/lib/i18n";
import { BAR, COMPONENTS, LABEL } from "@/lib/types-performance";
import type { RankingRow } from "@/lib/types-performance";

export function RankingTable({ rows, selected, onSelect }: { rows: RankingRow[]; selected: number | null; onSelect: (id: number) => void }) {
  return (
    <section aria-labelledby="rank-h" className="panel min-w-0 overflow-hidden">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line px-5 py-3.5">
        <h2 id="rank-h" className="text-[15px] font-semibold"><T>Ranking</T></h2>
        {COMPONENTS.map((k) => (
          <span key={k} className="flex items-center gap-1.5 text-[12px] text-ink-3">
            <span aria-hidden="true" className="size-2.5 rounded-[2px]" style={{ background: BAR[k] }} />
            <T>{LABEL[k]}</T>
          </span>
        ))}
      </div>
      {rows.length === 0 ? (
        <Empty title="No production in this period" text="Rankings appear once workers have production entries for the selected period and group." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-[14px]">
            <thead>
              <tr className="text-left text-[12px] text-ink-3">
                <th scope="col" className="w-12 px-5 py-2.5 font-medium">#</th>
                <th scope="col" className="px-2 py-2.5 font-medium"><T>Worker</T></th>
                <th scope="col" className="w-[36%] px-2 py-2.5 font-medium"><T>Score</T></th>
                <th scope="col" className="px-2 py-2.5 text-right font-medium"><T>Efficiency</T></th>
                <th scope="col" className="px-2 py-2.5 text-right font-medium"><T>First pass</T></th>
                <th scope="col" className="px-5 py-2.5 text-right font-medium"><T>Coverage</T></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Row key={r.worker.id} r={r} active={selected === r.worker.id} onSelect={onSelect} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Row({ r, active, onSelect }: { r: RankingRow; active: boolean; onSelect: (id: number) => void }) {
  const excluded = !r.eligible;
  return (
    <tr
      className={`cursor-pointer border-t border-line hover:bg-sunk/60 ${active ? "bg-brand-bg font-medium" : ""} ${excluded ? "text-ink-3" : ""}`}
      onClick={() => onSelect(r.worker.id)}
    >
      <td className="px-5 py-3 font-mono text-ink-3 tabular">{r.rank ?? "—"}</td>
      <td className="px-2 py-3">
        <button
          type="button"
          aria-pressed={active}
          className="flex flex-col text-left focus-visible:outline-2 focus-visible:outline-brand"
          onClick={(e) => {
            e.stopPropagation();
            onSelect(r.worker.id);
          }}
        >
          <span className="font-medium">{r.worker.name}</span>
          <span className="font-mono text-[12px] text-ink-3">
            {r.worker.code}
            {excluded && <> · {r.exclusion_reason}</>}
          </span>
        </button>
      </td>
      <td className="px-2 py-3">
        <span className="flex items-center gap-3">
          <span
            role="img"
            aria-label={excluded ? "No score" : COMPONENTS.map((k) => `${LABEL[k]} ${r.contributions?.[k] ?? 0}`).join(", ")}
            className="flex h-3 flex-1 overflow-hidden rounded-[3px] bg-sunk"
          >
            {!excluded &&
              COMPONENTS.map((k) => <span key={k} className="block h-full" style={{ width: `${r.contributions?.[k] ?? 0}%`, background: BAR[k] }} />)}
          </span>
          <span className="w-11 text-right font-mono font-medium tabular">{r.total == null ? "—" : r.total.toFixed(1)}</span>
        </span>
      </td>
      <td className="px-2 py-3 text-right font-mono tabular">{excluded ? "—" : pct(r.efficiency_pct)}</td>
      <td className="px-2 py-3 text-right font-mono tabular">{excluded ? "—" : pct(r.first_pass_pct)}</td>
      <td className="px-5 py-3 text-right font-mono tabular">{`${Math.round(r.coverage_pct)}%`}</td>
    </tr>
  );
}
