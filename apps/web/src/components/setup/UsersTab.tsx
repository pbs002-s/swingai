"use client";

import { useState } from "react";
import { patch, post } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { LineRow, ScopeType, UserRow } from "@/lib/types-setup";
import { Feedback, Field, Loaded, Section, Select, td, th, useAction, useFactories } from "@/components/setup/shared";

// Mirrors ROLES in apps/api/app/models/auth.py; the API rejects anything else.
const ROLES = ["system_admin", "factory_admin", "supervisor", "quality", "maintenance", "management"];
const label = (r: string) => r.replace(/_/g, " ");
const EMPTY = { email: "", full_name: "", password: "", role: "supervisor", scope_type: "all" as ScopeType, scope_id: "" };

function AddUser({ onDone }: { onDone: () => void }) {
  const factories = useFactories();
  const lines = useApi<LineRow[]>("/lines?limit=2000");
  const [v, setV] = useState(EMPTY);
  const act = useAction();
  const scopes = v.scope_type === "factory" ? (factories.data ?? []) : v.scope_type === "line" ? (lines.data ?? []) : [];
  return (
    <form
      aria-label="Add user"
      className="flex flex-wrap items-end gap-3 border-b border-line px-5 py-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const role = { role: v.role, scope_type: v.scope_type, scope_id: v.scope_type === "all" ? null : Number(v.scope_id) };
        const body = { email: v.email.trim(), full_name: v.full_name.trim(), password: v.password, roles: [role] };
        if (await act.run(() => post("/users", body), `Account for ${body.email} created. Share the password privately.`)) {
          setV(EMPTY);
          onDone();
        }
      }}
    >
      <Field label="Email" type="email" autoComplete="off" value={v.email} required maxLength={254} onChange={(e) => setV({ ...v, email: e.target.value })} className="w-56" />
      <Field label="Full name" value={v.full_name} required maxLength={120} onChange={(e) => setV({ ...v, full_name: e.target.value })} className="w-44" />
      <Field label="Password (12+ characters)" type="password" autoComplete="new-password" value={v.password} required minLength={12} maxLength={256} onChange={(e) => setV({ ...v, password: e.target.value })} className="w-52" />
      <Select label="Role" value={v.role} onChange={(x) => setV({ ...v, role: x })} className="w-40">
        {ROLES.map((r) => <option key={r} value={r}>{label(r)}</option>)}
      </Select>
      <Select label="Scope" value={v.scope_type} onChange={(x) => setV({ ...v, scope_type: x as ScopeType, scope_id: "" })} className="w-32">
        <option value="all">Everything</option>
        <option value="factory">One factory</option>
        <option value="line">One line</option>
      </Select>
      {v.scope_type !== "all" && (
        <Select label={v.scope_type === "line" ? "Line" : "Factory"} value={v.scope_id} required onChange={(x) => setV({ ...v, scope_id: x })} className="w-44">
          <option value="">Choose…</option>
          {scopes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
      )}
      <button type="submit" className="btn btn-brand btn-sm min-h-11" disabled={act.busy}>Add user</button>
      <Feedback msg={act.msg} />
    </form>
  );
}

function ResetPassword({ u }: { u: UserRow }) {
  const [open, setOpen] = useState(false);
  const [pw, setPw] = useState("");
  const act = useAction();
  if (!open)
    return (
      <span className="inline-flex flex-wrap items-center gap-2">
        <button type="button" className="btn btn-ghost btn-sm min-h-11" aria-label={`Reset password for ${u.email}`} onClick={() => setOpen(true)}>Reset password</button>
        <Feedback msg={act.msg} />
      </span>
    );
  return (
    <form
      className="inline-flex flex-wrap items-center gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        if (await act.run(() => post(`/users/${u.id}/reset-password`, { password: pw }), `Password reset; ${u.email} was logged out everywhere.`)) {
          setPw("");
          setOpen(false);
        }
      }}
    >
      <label className="sr-only" htmlFor={`pw-${u.id}`}>New password for {u.email}</label>
      <input id={`pw-${u.id}`} type="password" autoComplete="new-password" className="field min-h-11 w-44" minLength={12} maxLength={256} required value={pw} onChange={(e) => setPw(e.target.value)} />
      <button type="submit" className="btn btn-brand btn-sm min-h-11" disabled={act.busy}>Set</button>
      <button type="button" className="btn btn-ghost btn-sm min-h-11" onClick={() => setOpen(false)}>Cancel</button>
      <Feedback msg={act.msg} />
    </form>
  );
}

export function UsersTab({ meId }: { meId: number }) {
  const users = useApi<UserRow[]>("/users");
  const act = useAction();
  return (
    <Section title="Staff accounts" id="users-h">
      <AddUser onDone={users.refresh} />
      <div className="px-5"><Feedback msg={act.msg} /></div>
      <Loaded q={users} empty={{ title: "No users", text: "Add the first staff account above." }}>
        {(rows) => (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-[14px]">
              <thead>
                <tr><th className={th}>Name</th><th className={th}>Roles</th><th className={th}>Status</th><th className={th}><span className="sr-only">Actions</span></th></tr>
              </thead>
              <tbody>
                {rows.map((u) => (
                  <tr key={u.id} className={u.is_active ? "" : "text-ink-3"}>
                    <td className={td}>
                      <span className="flex flex-col"><span className="font-medium">{u.full_name}</span><span className="text-[12px] text-ink-3">{u.email}</span></span>
                    </td>
                    <td className={td}>
                      {u.roles.map((r) => `${label(r.role)}${r.scope_type === "all" ? "" : ` (${r.scope_type} ${r.scope_id})`}`).join(", ")}
                    </td>
                    <td className={td}>{u.is_active ? "active" : "deactivated"}</td>
                    <td className={`${td} whitespace-nowrap text-right`}>
                      {u.id !== meId && (
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm min-h-11"
                          aria-label={`${u.is_active ? "Deactivate" : "Reactivate"} ${u.email}`}
                          onClick={() => void act.run(async () => { await patch(`/users/${u.id}`, { is_active: !u.is_active }); void users.refresh(); }, `${u.email} ${u.is_active ? "deactivated" : "reactivated"}.`)}
                        >
                          {u.is_active ? "Deactivate" : "Reactivate"}
                        </button>
                      )}{" "}
                      <ResetPassword u={u} />
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
