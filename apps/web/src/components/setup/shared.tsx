"use client";

import { useState } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { ApiFailure } from "@/lib/api";
import type { Factory } from "@/lib/types-setup";
import { useApi } from "@/lib/hooks";
import { Empty, ErrorBox, Loading } from "@/components/app/ui";

export type Msg = { ok: boolean; text: string } | null;

export const errText = (e: unknown) => (e instanceof ApiFailure ? e.message : "Something went wrong. Try again.");

/** Runs one save at a time and keeps the last outcome as a message for the user. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  async function run<T>(fn: () => Promise<T>, done: string | ((result: T) => string)): Promise<boolean> {
    setBusy(true);
    setMsg(null);
    try {
      const result = await fn();
      setMsg({ ok: true, text: typeof done === "string" ? done : done(result) });
      return true;
    } catch (e) {
      setMsg({ ok: false, text: errText(e) });
      return false;
    } finally {
      setBusy(false);
    }
  }
  return { busy, msg, run };
}

export function Feedback({ msg }: { msg: Msg }) {
  if (!msg) return null;
  return msg.ok ? (
    <p role="status" className="text-[13px] text-run">{msg.text}</p>
  ) : (
    <p role="alert" className="text-[13px] text-down">{msg.text}</p>
  );
}

export function Section({ title, id, actions, children }: { title: string; id: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="panel overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3.5">
        <h2 id={id} className="text-[15px] font-semibold">{title}</h2>
        {actions && <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

type FieldProps = { label: string; className?: string } & InputHTMLAttributes<HTMLInputElement>;

export function Field({ label, className = "", ...input }: FieldProps) {
  return (
    <label className={`flex min-w-0 flex-col gap-1 text-[13px] text-ink-2 ${className}`}>
      {label}
      <input {...input} className="field" />
    </label>
  );
}

export function Select({
  label,
  value,
  onChange,
  children,
  className = "",
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: ReactNode;
  className?: string;
  required?: boolean;
}) {
  return (
    <label className={`flex min-w-0 flex-col gap-1 text-[13px] text-ink-2 ${className}`}>
      {label}
      <select value={value} required={required} onChange={(e) => onChange(e.target.value)} className="field">
        {children}
      </select>
    </label>
  );
}

/** Loading / error / empty wrapper for a useApi result. */
export function Loaded<T>({
  q,
  empty,
  children,
}: {
  q: { data: T[] | null; error: ApiFailure | null; loading: boolean; refresh: () => void };
  empty: { title: string; text: string };
  children: (rows: T[]) => ReactNode;
}) {
  if (q.error) return <div className="p-4"><ErrorBox message={q.error.message} onRetry={q.refresh} /></div>;
  if (q.loading && !q.data) return <div className="p-4"><Loading /></div>;
  if (!q.data?.length) return <Empty {...empty} />;
  return <>{children(q.data)}</>;
}

/** A name with Rename → input + Save in place. `onSave` throws on failure (shown inline). */
export function InlineName({ label, value, onSave, disabled }: { label: string; value: string; onSave: (v: string) => Promise<unknown>; disabled?: boolean }) {
  const [draft, setDraft] = useState<string | null>(null);
  const act = useAction();
  if (draft === null)
    return (
      <span className="flex min-w-0 flex-wrap items-center gap-2">
        <span className="truncate">{value}</span>
        {!disabled && (
          <button type="button" className="btn btn-ghost btn-sm min-h-11 sm:min-h-9" aria-label={`Rename ${label}`} onClick={() => setDraft(value)}>
            Rename
          </button>
        )}
        <Feedback msg={act.msg} />
      </span>
    );
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        if (await act.run(() => onSave(draft.trim()), "Renamed.")) setDraft(null);
      }}
    >
      <label className="sr-only" htmlFor={`rename-${label}`}>New name for {label}</label>
      <input id={`rename-${label}`} className="field min-h-11 w-56" value={draft} maxLength={120} required onChange={(e) => setDraft(e.target.value)} />
      <button type="submit" className="btn btn-brand btn-sm min-h-11" disabled={act.busy}>Save</button>
      <button type="button" className="btn btn-ghost btn-sm min-h-11" onClick={() => setDraft(null)}>Cancel</button>
      <Feedback msg={act.msg} />
    </form>
  );
}

export const th ="px-4 py-2.5 text-left text-[12px] font-medium text-ink-3";
export const td = "border-t border-line px-4 py-2.5 align-middle";

/** The install's factories; most installs have one, so forms default to the first. */
export function useFactories() {
  return useApi<Factory[]>("/factories");
}
