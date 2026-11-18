"use client";

import { useState } from "react";
import { patch, post } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { MachineBrand, MachineRow, MachineType, StationRow, StationStatus } from "@/lib/types-setup";
import { Feedback, Field, Loaded, Section, Select, td, th, useAction, useFactories } from "@/components/setup/shared";

const STATUSES: StationStatus[] = ["active", "maintenance", "inactive"];
type Draft = { asset_code: string; machine_type: string; brand: string; model: string; status: StationStatus };
const EMPTY: Draft = { asset_code: "", machine_type: "", brand: "", model: "", status: "active" };

function MachineForm({ editing, onDone }: { editing: MachineRow | null; onDone: () => void }) {
  const factories = useFactories();
  const types = useApi<MachineType[]>("/catalog/machine-types");
  const brands = useApi<MachineBrand[]>("/catalog/machine-brands");
  const [d, setD] = useState<Draft>(editing ? { ...editing, model: editing.model ?? "" } : EMPTY);
  const act = useAction();
  const activeTypes = types.data?.filter((t) => t.is_active || t.code === d.machine_type) ?? [];
  const activeBrands = brands.data?.filter((b) => b.is_active || b.name === d.brand) ?? [];
  const noLists = types.data && brands.data && (!activeTypes.length || !activeBrands.length);

  return (
    <form
      className="flex flex-wrap items-end gap-3 border-b border-line px-5 py-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const body = { machine_type: d.machine_type, brand: d.brand, model: d.model.trim() || null, status: d.status };
        const ok = await act.run(
          () =>
            editing
              ? patch(`/machines/${editing.id}`, body)
              : post("/machines", { ...body, asset_code: d.asset_code.trim(), factory_id: factories.data?.[0]?.id }),
          editing ? `${editing.asset_code} saved.` : `Machine ${d.asset_code} added.`,
        );
        if (ok) {
          if (!editing) setD(EMPTY);
          onDone();
        }
      }}
    >
      {noLists && <p className="w-full text-[13px] text-ink-3">Add machine types and brands in the Lists tab first.</p>}
      {!editing && <Field label="Asset code" value={d.asset_code} required maxLength={32} onChange={(e) => setD({ ...d, asset_code: e.target.value })} className="w-36" />}
      <Select label="Machine type" value={d.machine_type} required onChange={(v) => setD({ ...d, machine_type: v })} className="w-44">
        <option value="">Choose…</option>
        {activeTypes.map((t) => <option key={t.id} value={t.code}>{t.name}</option>)}
      </Select>
      <Select label="Brand" value={d.brand} required onChange={(v) => setD({ ...d, brand: v })} className="w-44">
        <option value="">Choose…</option>
        {activeBrands.map((b) => <option key={b.id} value={b.name}>{b.name}</option>)}
      </Select>
      <Field label="Model (optional)" value={d.model} maxLength={64} onChange={(e) => setD({ ...d, model: e.target.value })} className="w-40" />
      <Select label="Status" value={d.status} onChange={(v) => setD({ ...d, status: v as StationStatus })} className="w-36">
        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
      </Select>
      <button type="submit" className="btn btn-brand btn-sm min-h-11" disabled={act.busy}>{editing ? "Save machine" : "Add machine"}</button>
      {editing && <button type="button" className="btn btn-ghost btn-sm min-h-11" onClick={onDone}>Cancel</button>}
      <Feedback msg={act.msg} />
    </form>
  );
}

function AssignRow({ m, stations, onDone }: { m: MachineRow; stations: StationRow[]; onDone: () => void }) {
  const [stationId, setStationId] = useState(m.station ? String(m.station.id) : "");
  const act = useAction();
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        if (await act.run(() => post(`/machines/${m.id}/assign`, { station_id: Number(stationId) }), `${m.asset_code} placed.`)) onDone();
      }}
    >
      <label className="sr-only" htmlFor={`place-${m.id}`}>Station for {m.asset_code}</label>
      <select id={`place-${m.id}`} className="field min-h-11 w-36" value={stationId} required onChange={(e) => setStationId(e.target.value)}>
        <option value="">Not placed</option>
        {stations.map((s) => <option key={s.id} value={s.id}>{s.code}</option>)}
      </select>
      <button type="submit" className="btn btn-ghost btn-sm min-h-11" disabled={act.busy || !stationId || stationId === String(m.station?.id ?? "")}>Place</button>
      <Feedback msg={act.msg} />
    </form>
  );
}

export function MachinesTab({ canEdit }: { canEdit: boolean }) {
  const [q, setQ] = useState("");
  const machines = useApi<MachineRow[]>(`/machines${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ""}`);
  const stations = useApi<StationRow[]>("/stations?limit=2000");
  const types = useApi<MachineType[]>("/catalog/machine-types");
  const [editing, setEditing] = useState<MachineRow | null>(null);
  const typeName = (code: string) => types.data?.find((t) => t.code === code)?.name ?? code;

  return (
    <Section
      title="Machines"
      id="machines-h"
      actions={
        <label className="flex items-center gap-2 text-[13px] text-ink-2">
          Search
          <input type="search" className="field min-h-11 w-48" value={q} maxLength={60} placeholder="Asset, brand, model" onChange={(e) => setQ(e.target.value)} />
        </label>
      }
    >
      {canEdit && <MachineForm key={editing?.id ?? "new"} editing={editing} onDone={() => { setEditing(null); void machines.refresh(); }} />}
      <Loaded q={machines} empty={{ title: "No machines", text: q ? "Nothing matches that search." : "Add a machine above or import machines.csv." }}>
        {(rows) => (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-[14px]">
              <thead>
                <tr>
                  <th className={th}>Asset</th><th className={th}>Type</th><th className={th}>Brand</th><th className={th}>Model</th>
                  <th className={th}>Status</th><th className={th}>Station</th>
                  {canEdit && <th className={th}><span className="sr-only">Actions</span></th>}
                </tr>
              </thead>
              <tbody>
                {rows.map((m) => (
                  <tr key={m.id}>
                    <td className={`${td} font-mono`}>{m.asset_code}</td>
                    <td className={td}>{typeName(m.machine_type)}</td>
                    <td className={td}>{m.brand}</td>
                    <td className={td}>{m.model ?? "—"}</td>
                    <td className={td}>{m.status}</td>
                    <td className={td}>
                      {canEdit ? <AssignRow m={m} stations={stations.data ?? []} onDone={machines.refresh} /> : (m.station?.code ?? "—")}
                    </td>
                    {canEdit && (
                      <td className={td}>
                        <button type="button" className="btn btn-ghost btn-sm min-h-11" aria-label={`Edit ${m.asset_code}`} onClick={() => setEditing(m)}>Edit</button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Loaded>
    </Section>
  );
}
