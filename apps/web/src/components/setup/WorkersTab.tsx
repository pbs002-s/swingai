"use client";

import { useState } from "react";
import { api, patch, post } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { AssignmentRow, Operation, StationRow, WorkerListRow, WorkerRow } from "@/lib/types-setup";
import { Feedback, Field, Loaded, Section, Select, errText, td, th, useAction, useFactories } from "@/components/setup/shared";

type Draft = { employee_code: string; full_name: string; full_name_bn: string; rfid_card_id: string; is_active: boolean };
const EMPTY: Draft = { employee_code: "", full_name: "", full_name_bn: "", rfid_card_id: "", is_active: true };

function WorkerForm({ editing, onDone }: { editing: WorkerRow | null; onDone: () => void }) {
  const factories = useFactories();
  const [d, setD] = useState<Draft>(
    editing
      ? { employee_code: editing.employee_code, full_name: editing.full_name, full_name_bn: editing.full_name_bn ?? "", rfid_card_id: editing.rfid_card_id ?? "", is_active: editing.is_active }
      : EMPTY,
  );
  const act = useAction();
  return (
    <form
      className="flex flex-wrap items-end gap-3 border-b border-line px-5 py-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const body = { full_name: d.full_name.trim(), full_name_bn: d.full_name_bn.trim() || null, rfid_card_id: d.rfid_card_id.trim() || null };
        const ok = await act.run(
          () =>
            editing
              ? patch(`/workers/${editing.id}`, { ...body, is_active: d.is_active })
              : post("/workers", { ...body, employee_code: d.employee_code.trim(), factory_id: factories.data?.[0]?.id }),
          editing ? `${editing.employee_code} saved.` : `Worker ${d.employee_code} added.`,
        );
        if (ok) {
          if (!editing) setD(EMPTY);
          onDone();
        }
      }}
    >
      {!editing && <Field label="Employee code" value={d.employee_code} required maxLength={32} onChange={(e) => setD({ ...d, employee_code: e.target.value })} className="w-36" />}
      <Field label="Full name" value={d.full_name} required maxLength={120} onChange={(e) => setD({ ...d, full_name: e.target.value })} className="w-48" />
      <Field label="Name in Bangla (optional)" lang="bn" value={d.full_name_bn} maxLength={120} onChange={(e) => setD({ ...d, full_name_bn: e.target.value })} className="w-48" />
      <Field label="Card ID (optional)" value={d.rfid_card_id} maxLength={64} pattern="[A-Za-z0-9\-]*" onChange={(e) => setD({ ...d, rfid_card_id: e.target.value })} className="w-36" />
      {editing && (
        <label className="flex min-h-11 items-center gap-2 text-[14px]">
          <input type="checkbox" className="size-4 accent-[var(--brand)]" checked={d.is_active} onChange={(e) => setD({ ...d, is_active: e.target.checked })} />
          Active
        </label>
      )}
      <button type="submit" className="btn btn-brand btn-sm min-h-11" disabled={act.busy}>{editing ? "Save worker" : "Add worker"}</button>
      {editing && <button type="button" className="btn btn-ghost btn-sm min-h-11" onClick={onDone}>Cancel</button>}
      <Feedback msg={act.msg} />
    </form>
  );
}

function AssignForm({ workers, onDone }: { workers: WorkerListRow[]; onDone: () => void }) {
  const stations = useApi<StationRow[]>("/stations?limit=2000");
  const ops = useApi<Operation[]>("/operations?limit=2000");
  const [v, setV] = useState({ worker_id: "", station_id: "", operation_id: "" });
  const act = useAction();
  return (
    <form
      aria-label="Assign worker"
      className="flex flex-wrap items-end gap-3 border-b border-line px-5 py-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const body = { worker_id: Number(v.worker_id), station_id: Number(v.station_id), operation_id: Number(v.operation_id) };
        if (await act.run(() => post("/assignments", body), "Assignment saved. The worker's previous station assignment was closed.")) onDone();
      }}
    >
      <Select label="Worker" value={v.worker_id} required onChange={(x) => setV({ ...v, worker_id: x })} className="w-52">
        <option value="">Choose…</option>
        {workers.map((w) => <option key={w.id} value={w.id}>{w.employee_code} · {w.full_name}</option>)}
      </Select>
      <Select label="Station" value={v.station_id} required onChange={(x) => setV({ ...v, station_id: x })} className="w-36">
        <option value="">Choose…</option>
        {stations.data?.filter((s) => s.status !== "inactive").map((s) => <option key={s.id} value={s.id}>{s.code}</option>)}
      </Select>
      <Select label="Operation" value={v.operation_id} required onChange={(x) => setV({ ...v, operation_id: x })} className="w-52">
        <option value="">Choose…</option>
        {ops.data?.map((o) => <option key={o.id} value={o.id}>{o.name} ({o.code})</option>)}
      </Select>
      <button type="submit" className="btn btn-ghost btn-sm min-h-11" disabled={act.busy}>Assign</button>
      <Feedback msg={act.msg} />
    </form>
  );
}

export function WorkersTab({ canEdit }: { canEdit: boolean }) {
  const [q, setQ] = useState("");
  const workers = useApi<WorkerListRow[]>(`/workers?limit=200${q.trim() ? `&q=${encodeURIComponent(q.trim())}` : ""}`);
  const assignments = useApi<AssignmentRow[]>("/assignments?active=true&limit=2000");
  const [editing, setEditing] = useState<WorkerRow | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const end = useAction();
  const current = new Map((assignments.data ?? []).map((a) => [a.worker_id, a]));
  const refresh = () => { void workers.refresh(); void assignments.refresh(); };

  async function startEdit(id: number) {
    setLoadErr(null);
    try {
      const { data } = await api<WorkerRow>(`/workers/${id}`);
      setEditing(data);
    } catch (e) {
      setLoadErr(errText(e));
    }
  }

  return (
    <Section
      title="Workers"
      id="workers-h"
      actions={
        <label className="flex items-center gap-2 text-[13px] text-ink-2">
          Search
          <input type="search" className="field min-h-11 w-48" value={q} maxLength={60} placeholder="Name or code" onChange={(e) => setQ(e.target.value)} />
        </label>
      }
    >
      {canEdit && <WorkerForm key={editing?.id ?? "new"} editing={editing} onDone={() => { setEditing(null); refresh(); }} />}
      {canEdit && workers.data && workers.data.length > 0 && <AssignForm workers={workers.data} onDone={refresh} />}
      <div className="px-5"><Feedback msg={loadErr ? { ok: false, text: loadErr } : end.msg} /></div>
      <Loaded q={workers} empty={{ title: "No workers", text: q ? "Nothing matches that search." : "Add a worker above or import workers.csv." }}>
        {(rows) => (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-[14px]">
              <thead>
                <tr>
                  <th className={th}>Code</th><th className={th}>Name</th><th className={th}>Station · operation</th>
                  {canEdit && <th className={th}><span className="sr-only">Actions</span></th>}
                </tr>
              </thead>
              <tbody>
                {rows.map((w) => {
                  const a = current.get(w.id);
                  return (
                    <tr key={w.id}>
                      <td className={`${td} font-mono`}>{w.employee_code}</td>
                      <td className={td}>{w.full_name}{w.full_name_bn && <span lang="bn" className="ml-2 text-ink-3">{w.full_name_bn}</span>}</td>
                      <td className={td}>{a ? `${a.station.code} · ${a.operation.name}` : "—"}</td>
                      {canEdit && (
                        <td className={`${td} whitespace-nowrap text-right`}>
                          <button type="button" className="btn btn-ghost btn-sm min-h-11" aria-label={`Edit ${w.employee_code}`} onClick={() => void startEdit(w.id)}>Edit</button>{" "}
                          {a && (
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm min-h-11"
                              aria-label={`End assignment of ${w.employee_code}`}
                              onClick={() => void end.run(async () => { await post(`/assignments/${a.id}/end`); refresh(); }, `${w.employee_code} unassigned from ${a.station.code}.`)}
                            >
                              Unassign
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Loaded>
    </Section>
  );
}
