"use client";

import { useState } from "react";
import { patch, post } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { Factory, FloorRow, LineRow, StationRow, StationStatus } from "@/lib/types-setup";
import { Feedback, Field, InlineName, Loaded, Section, Select, td, th, useAction, useFactories } from "@/components/setup/shared";

const STATUSES: StationStatus[] = ["active", "maintenance", "inactive"];

function FactoryCard({ f, canEdit, onSaved }: { f: Factory; canEdit: boolean; onSaved: () => void }) {
  const [tz, setTz] = useState(f.timezone);
  const [cardTap, setCardTap] = useState(!!f.settings.card_tap_enabled);
  const [blur, setBlur] = useState(!!f.settings.face_blur);
  const act = useAction();
  return (
    <div className="flex flex-col gap-3 border-b border-line px-5 py-4 last:border-b-0">
      <div className="text-[15px] font-medium">
        <InlineName label={`factory ${f.code}`} value={f.name} disabled={!canEdit} onSave={async (name) => { await patch(`/factories/${f.id}`, { name }); onSaved(); }} />
      </div>
      <form
        className="flex flex-wrap items-end gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          void act.run(async () => {
            await patch(`/factories/${f.id}`, { timezone: tz.trim(), settings: { card_tap_enabled: cardTap, face_blur: blur } });
            onSaved();
          }, "Factory settings saved.");
        }}
      >
        <Field label="Time zone (IANA, e.g. Asia/Dhaka)" value={tz} disabled={!canEdit} required onChange={(e) => setTz(e.target.value)} className="w-64" />
        <label className="flex min-h-11 items-center gap-2 text-[14px]">
          <input type="checkbox" className="size-4 accent-[var(--brand)]" disabled={!canEdit} checked={cardTap} onChange={(e) => setCardTap(e.target.checked)} />
          Worker card tap
        </label>
        <label className="flex min-h-11 items-center gap-2 text-[14px]">
          <input type="checkbox" className="size-4 accent-[var(--brand)]" disabled={!canEdit} checked={blur} onChange={(e) => setBlur(e.target.checked)} />
          Blur faces in clips
        </label>
        {canEdit && <button type="submit" className="btn btn-brand btn-sm min-h-11" disabled={act.busy}>Save settings</button>}
      </form>
      <Feedback msg={act.msg} />
    </div>
  );
}

function AddForm({ label, fields, onAdd }: { label: string; fields: string[]; onAdd: (values: Record<string, string>) => Promise<unknown> }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const act = useAction();
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={async (e) => {
        e.preventDefault();
        if (await act.run(() => onAdd(values), `${label} added.`)) setValues({});
      }}
    >
      {fields.map((f) => (
        <Field key={f} label={`${label} ${f}`} value={values[f] ?? ""} required onChange={(e) => setValues({ ...values, [f]: e.target.value })} className="w-40" />
      ))}
      <button type="submit" className="btn btn-ghost btn-sm min-h-11" disabled={act.busy}>Add {label.toLowerCase()}</button>
      <Feedback msg={act.msg} />
    </form>
  );
}

function Stations({ line, canEdit }: { line: LineRow; canEdit: boolean }) {
  const q = useApi<StationRow[]>(`/stations?line_id=${line.id}&limit=2000`);
  const [bulk, setBulk] = useState({ prefix: `${line.code}-S`, start: "1", count: "10" });
  const act = useAction();
  const status = useAction();
  return (
    <Section title={`Stations on ${line.name}`} id="stations-h">
      {canEdit && (
        <form
          className="flex flex-wrap items-end gap-3 border-b border-line px-5 py-4"
          onSubmit={(e) => {
            e.preventDefault();
            void act.run(async () => {
              const { data } = await post<{ created: number; first: string; last: string }>("/stations/bulk", {
                line_id: line.id,
                prefix: bulk.prefix.trim(),
                start: Number(bulk.start),
                count: Number(bulk.count),
              });
              void q.refresh();
              return data;
            }, (d) => `Added ${d.created} stations (${d.first} – ${d.last}).`);
          }}
        >
          <Field label="Code prefix" value={bulk.prefix} required maxLength={16} pattern="[A-Za-z0-9\-]+" onChange={(e) => setBulk({ ...bulk, prefix: e.target.value })} className="w-36" />
          <Field label="Start number" type="number" min={1} max={9999} value={bulk.start} required onChange={(e) => setBulk({ ...bulk, start: e.target.value })} className="w-28" />
          <Field label="How many" type="number" min={1} max={500} value={bulk.count} required onChange={(e) => setBulk({ ...bulk, count: e.target.value })} className="w-28" />
          <button type="submit" className="btn btn-brand btn-sm min-h-11" disabled={act.busy}>Add stations</button>
          <Feedback msg={act.msg} />
        </form>
      )}
      <Feedback msg={status.msg} />
      <Loaded q={q} empty={{ title: "No stations yet", text: "Add stations in bulk above, or import org_structure.csv." }}>
        {(rows) => (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-[14px]">
              <thead><tr><th className={th}>Code</th><th className={th}>Name</th><th className={th}>Status</th></tr></thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id}>
                    <td className={`${td} font-mono`}>{s.code}</td>
                    <td className={td}>
                      <InlineName label={`station ${s.code}`} value={s.name} disabled={!canEdit} onSave={async (name) => { await patch(`/stations/${s.id}`, { name }); void q.refresh(); }} />
                    </td>
                    <td className={td}>
                      <label className="sr-only" htmlFor={`st-${s.id}`}>Status of {s.code}</label>
                      <select
                        id={`st-${s.id}`}
                        className="field min-h-11 w-40"
                        disabled={!canEdit}
                        value={s.status}
                        onChange={(e) => void status.run(async () => { await patch(`/stations/${s.id}`, { status: e.target.value }); void q.refresh(); }, `${s.code} set to ${e.target.value}.`)}
                      >
                        {STATUSES.map((v) => <option key={v} value={v}>{v}</option>)}
                      </select>
                    </td>
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

export function StructureTab({ canEdit }: { canEdit: boolean }) {
  const factories = useFactories();
  const floors = useApi<FloorRow[]>("/floors?limit=2000");
  const lines = useApi<LineRow[]>("/lines?limit=2000");
  const [lineId, setLineId] = useState<string>("");
  const lineAct = useAction();
  const factoryId = factories.data?.[0]?.id;
  const picked = lines.data?.find((l) => String(l.id) === lineId);

  async function toggleLine(l: LineRow) {
    await lineAct.run(async () => { await patch(`/lines/${l.id}`, { is_active: !l.is_active }); void lines.refresh(); }, `${l.name} ${l.is_active ? "deactivated" : "reactivated"}.`);
  }

  return (
    <div className="flex flex-col gap-5">
      <Section title="Factory" id="factory-h">
        <Loaded q={factories} empty={{ title: "No factory yet", text: "Create the factory first; everything else hangs off it." }}>
          {(rows) => rows.map((f) => <FactoryCard key={f.id} f={f} canEdit={canEdit} onSaved={factories.refresh} />)}
        </Loaded>
        {canEdit && !factories.data?.length && !factories.loading && (
          <div className="px-5 pb-4">
            <AddForm label="Factory" fields={["code", "name"]} onAdd={async (v) => { await post("/factories", v); void factories.refresh(); }} />
          </div>
        )}
      </Section>

      <Section title="Floors and lines" id="floors-h">
        <Loaded q={floors} empty={{ title: "No floors yet", text: "Add a floor, then its lines." }}>
          {(rows) => (
            <ul>
              {rows.map((fl) => (
                <li key={fl.id} className="flex flex-col gap-3 border-b border-line px-5 py-4">
                  <div className="text-[15px] font-medium">
                    <span className="mr-2 font-mono text-[12px] text-ink-3">{fl.code}</span>
                    <InlineName label={`floor ${fl.code}`} value={fl.name} disabled={!canEdit} onSave={async (name) => { await patch(`/floors/${fl.id}`, { name }); void floors.refresh(); }} />
                  </div>
                  <ul className="flex flex-col gap-1 pl-4">
                    {lines.data?.filter((l) => l.floor_id === fl.id).map((l) => (
                      <li key={l.id} className={`flex flex-wrap items-center gap-3 text-[14px] ${l.is_active ? "" : "text-ink-3"}`}>
                        <span className="font-mono text-[12px] text-ink-3">{l.code}</span>
                        <InlineName label={`line ${l.code}`} value={l.name} disabled={!canEdit} onSave={async (name) => { await patch(`/lines/${l.id}`, { name }); void lines.refresh(); }} />
                        {!l.is_active && <span className="rounded-md bg-off-bg px-2 py-0.5 text-[12px]">inactive</span>}
                        <button type="button" className="btn btn-ghost btn-sm min-h-11 sm:min-h-9" onClick={() => setLineId(String(l.id))}>Stations</button>
                        {canEdit && (
                          <button type="button" className="btn btn-ghost btn-sm min-h-11 sm:min-h-9" onClick={() => void toggleLine(l)}>
                            {l.is_active ? "Deactivate" : "Reactivate"}
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                  {canEdit && (
                    <AddForm label="Line" fields={["code", "name"]} onAdd={async (v) => { await post("/lines", { floor_id: fl.id, ...v }); void lines.refresh(); }} />
                  )}
                </li>
              ))}
            </ul>
          )}
        </Loaded>
        <div className="flex flex-col gap-2 px-5 py-4">
          <Feedback msg={lineAct.msg} />
          {canEdit && factoryId && (
            <AddForm label="Floor" fields={["code", "name"]} onAdd={async (v) => { await post("/floors", { factory_id: factoryId, ...v }); void floors.refresh(); }} />
          )}
        </div>
      </Section>

      {lines.data && lines.data.length > 0 && (
        <div className="flex flex-col gap-3">
          <Select label="Show stations for line" value={lineId} onChange={setLineId} className="max-w-xs">
            <option value="">Pick a line…</option>
            {lines.data.map((l) => <option key={l.id} value={l.id}>{l.name} ({l.code})</option>)}
          </Select>
          {picked && <Stations key={picked.id} line={picked} canEdit={canEdit} />}
        </div>
      )}
    </div>
  );
}
