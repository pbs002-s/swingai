"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiFailure, api } from "@/lib/api";
import { Empty, ErrorBox, Loading, PageHeader } from "@/components/app/ui";

type Row = {
  id: number;
  at: string;
  actor: { id: number; name: string; email: string } | null;
  action: string;
  entity: string;
  entity_id: string | null;
  detail: Record<string, unknown> | null;
  ip: string | null;
};

const PAGE = 50;

export default function AuditPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [action, setAction] = useState("");
  const [entity, setEntity] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (before: number | null) => {
    setLoading(true);
    setError(null);
    const q = new URLSearchParams({ limit: String(PAGE) });
    if (action.trim()) q.set("action", action.trim());
    if (entity.trim()) q.set("entity", entity.trim());
    if (before) q.set("before_id", String(before));
    try {
      const res = await api<Row[]>(`/audit-logs?${q}`);
      setRows((prev) => (before ? [...prev, ...res.data] : res.data));
      setNext((res.meta.next_before_id as number | null) ?? null);
    } catch (e) {
      setError(e instanceof ApiFailure ? e.message : "Could not load the audit log.");
    } finally {
      setLoading(false);
    }
  }, [action, entity]);

  useEffect(() => {
    const id = setTimeout(() => void load(null), 300); // wait for typing to pause
    return () => clearTimeout(id);
  }, [load]);

  return (
    <>
      <PageHeader
        title="Audit log"
        sub="Who changed what, newest first. Entries cannot be edited or deleted."
        actions={
          <>
            <label className="flex items-center gap-2 text-[13px]">
              Action starts with
              <input className="field w-40" value={action} onChange={(e) => setAction(e.target.value)} placeholder="camera" />
            </label>
            <label className="flex items-center gap-2 text-[13px]">
              Entity
              <input className="field w-32" value={entity} onChange={(e) => setEntity(e.target.value)} placeholder="device" />
            </label>
          </>
        }
      />
      {error && <ErrorBox message={error} onRetry={() => void load(null)} />}
      {loading && rows.length === 0 ? (
        <Loading />
      ) : rows.length === 0 ? (
        !error && <Empty title="No entries" text="Nothing matches these filters." />
      ) : (
        <section aria-label="Audit entries" className="panel overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead className="border-b border-line text-[12px] text-ink-3">
              <tr>
                {["When", "Who", "Action", "What", "Details", "From"].map((h) => (
                  <th key={h} scope="col" className="px-3 py-2 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-line align-top">
                  <td className="whitespace-nowrap px-3 py-2 font-mono">{new Date(r.at).toLocaleString()}</td>
                  <td className="px-3 py-2">{r.actor ? r.actor.name : "System"}</td>
                  <td className="px-3 py-2 font-mono">{r.action}</td>
                  <td className="px-3 py-2">{r.entity}{r.entity_id ? ` #${r.entity_id}` : ""}</td>
                  <td className="max-w-md break-words px-3 py-2 font-mono text-[12px] text-ink-2">{r.detail ? JSON.stringify(r.detail) : ""}</td>
                  <td className="px-3 py-2 font-mono text-ink-3">{r.ip ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {next && (
            <div className="border-t border-line p-3">
              <button className="btn" onClick={() => void load(next)} disabled={loading}>Load older entries</button>
            </div>
          )}
        </section>
      )}
    </>
  );
}
