"use client";

import { useState } from "react";
import { patch, post } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { Feedback, Loaded, Section, td, th, useAction } from "@/components/setup/shared";

export type ListField = {
  key: string;
  label: string;
  /** "create": set only when adding (codes, parents); "both": also editable later. */
  mode: "create" | "both";
  required?: boolean;
  type?: "text" | "number";
  step?: string;
  options?: { value: string; label: string }[];
  show?: (row: Row) => string;
};
type Row = { id: number; is_active?: boolean } & Record<string, unknown>;

function toBody(fields: ListField[], values: Record<string, string>, forCreate: boolean) {
  const body: Record<string, unknown> = {};
  for (const f of fields) {
    if (!forCreate && f.mode !== "both") continue;
    const v = (values[f.key] ?? "").trim();
    if (!v) {
      if (!forCreate && !f.required) body[f.key] = null;
      continue;
    }
    body[f.key] = f.type === "number" && !f.step ? Number(v) : v;
  }
  return body;
}

function Input({ f, value, onChange, id }: { f: ListField; value: string; onChange: (v: string) => void; id: string }) {
  if (f.options)
    return (
      <select id={id} className="field min-h-11" value={value} required={f.required} onChange={(e) => onChange(e.target.value)}>
        <option value="">Choose…</option>
        {f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    );
  return <input id={id} className="field min-h-11" type={f.type ?? "text"} step={f.step} min={f.step ? f.step : undefined} value={value} required={f.required} onChange={(e) => onChange(e.target.value)} />;
}

/** One admin-editable list: table, inline edit, deactivate, and an add form. */
export function ListTable({ title, id, path, fields, canEdit }: { title: string; id: string; path: string; fields: ListField[]; canEdit: boolean }) {
  const q = useApi<Row[]>(`${path}${path.includes("?") ? "&" : "?"}limit=2000`);
  const [adding, setAdding] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<{ id: number; values: Record<string, string> } | null>(null);
  const add = useAction();
  const row = useAction();
  const base = path.split("?")[0];
  const hasActive = q.data?.some((r) => typeof r.is_active === "boolean");
  const cell = (r: Row, f: ListField) => (f.show ? f.show(r) : String(r[f.key] ?? "—"));

  return (
    <Section title={title} id={id}>
      {canEdit && (
        <form
          className="flex flex-wrap items-end gap-3 border-b border-line px-5 py-4"
          onSubmit={async (e) => {
            e.preventDefault();
            if (await add.run(() => post(base, toBody(fields, adding, true)), `${title}: added.`)) {
              setAdding({});
              void q.refresh();
            }
          }}
        >
          {fields.map((f) => (
            <label key={f.key} className="flex w-40 flex-col gap-1 text-[13px] text-ink-2" htmlFor={`${id}-new-${f.key}`}>
              {f.label}{f.required ? "" : " (optional)"}
              <Input f={f} id={`${id}-new-${f.key}`} value={adding[f.key] ?? ""} onChange={(v) => setAdding({ ...adding, [f.key]: v })} />
            </label>
          ))}
          <button type="submit" className="btn btn-brand btn-sm min-h-11" disabled={add.busy}>Add</button>
          <Feedback msg={add.msg} />
        </form>
      )}
      <div className="px-5"><Feedback msg={row.msg} /></div>
      <Loaded q={q} empty={{ title: "Nothing here yet", text: "Add the first entry above. Lists are used across the app." }}>
        {(rows) => (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-[14px]">
              <thead>
                <tr>
                  {fields.map((f) => <th key={f.key} className={th}>{f.label}</th>)}
                  {hasActive && <th className={th}>Status</th>}
                  {canEdit && <th className={th}><span className="sr-only">Actions</span></th>}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const isEditing = editing?.id === r.id;
                  return (
                    <tr key={r.id} className={r.is_active === false ? "text-ink-3" : ""}>
                      {fields.map((f) => (
                        <td key={f.key} className={td}>
                          {isEditing && f.mode === "both" ? (
                            <>
                              <label className="sr-only" htmlFor={`${id}-${r.id}-${f.key}`}>{f.label}</label>
                              <Input f={f} id={`${id}-${r.id}-${f.key}`} value={editing.values[f.key] ?? ""} onChange={(v) => setEditing({ id: r.id, values: { ...editing.values, [f.key]: v } })} />
                            </>
                          ) : (
                            cell(r, f)
                          )}
                        </td>
                      ))}
                      {hasActive && <td className={td}>{r.is_active ? "active" : "inactive"}</td>}
                      {canEdit && (
                        <td className={`${td} whitespace-nowrap text-right`}>
                          {isEditing ? (
                            <>
                              <button
                                type="button"
                                className="btn btn-brand btn-sm min-h-11"
                                disabled={row.busy}
                                onClick={async () => {
                                  if (await row.run(() => patch(`${base}/${r.id}`, toBody(fields, editing.values, false)), "Saved.")) {
                                    setEditing(null);
                                    void q.refresh();
                                  }
                                }}
                              >
                                Save
                              </button>{" "}
                              <button type="button" className="btn btn-ghost btn-sm min-h-11" onClick={() => setEditing(null)}>Cancel</button>
                            </>
                          ) : (
                            <>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm min-h-11"
                                aria-label={`Edit ${cell(r, fields[0])}`}
                                onClick={() => setEditing({ id: r.id, values: Object.fromEntries(fields.map((f) => [f.key, r[f.key] == null ? "" : String(r[f.key])])) })}
                              >
                                Edit
                              </button>
                              {typeof r.is_active === "boolean" && (
                                <>
                                  {" "}
                                  <button
                                    type="button"
                                    className="btn btn-ghost btn-sm min-h-11"
                                    aria-label={`${r.is_active ? "Deactivate" : "Reactivate"} ${cell(r, fields[0])}`}
                                    onClick={() => void row.run(async () => { await patch(`${base}/${r.id}`, { is_active: !r.is_active }); void q.refresh(); }, r.is_active ? "Deactivated." : "Reactivated.")}
                                  >
                                    {r.is_active ? "Deactivate" : "Reactivate"}
                                  </button>
                                </>
                              )}
                            </>
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
