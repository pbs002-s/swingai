"use client";

import { useState } from "react";
import { ApiFailure, post } from "@/lib/api";
import { hasRole, useMe } from "@/components/app/Shell";
import { ErrorBox, Loading, PageHeader } from "@/components/app/ui";
import { useApi } from "@/lib/hooks";

type Version = { version: number; body: Record<string, unknown>; effective_from?: string; effective_to?: string | null; default?: boolean };
type Policy = { kind: "shift" | "thresholds" | "retention"; name: string; current: Version; scheduled: Version | null; history: Version[] };
type Break = { start: string; end: string };

const when = (iso?: string) => (iso ? new Date(iso).toLocaleString() : "built-in default");
const toMin = (hhmm: string) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3));

function Panel({ policy, canEdit, onSaved, children, build }: {
  policy: Policy;
  canEdit: boolean;
  onSaved: () => void;
  children: React.ReactNode;
  build: () => Record<string, unknown>;
}) {
  const [effective, setEffective] = useState("");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      await post(`/policies/${policy.kind}`, {
        body: build(),
        note: note.trim() || undefined,
        effective_from: effective ? new Date(effective).toISOString() : undefined,
      });
      setMsg({ ok: true, text: effective ? "Change scheduled." : "New version saved and in force." });
      setEffective("");
      setNote("");
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof ApiFailure ? e.message : "Could not save." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby={`${policy.kind}-h`} className="panel grid content-start gap-4 p-5">
      <header>
        <h2 id={`${policy.kind}-h`} className="text-[16px] font-semibold">{policy.name}</h2>
        <p className="text-[13px] text-ink-3">
          Version {policy.current.version || "–"} in force since {when(policy.current.effective_from)}.
          {policy.scheduled && ` Next: version ${policy.scheduled.version} from ${when(policy.scheduled.effective_from)}.`}
        </p>
      </header>
      {children}
      {canEdit ? (
        <div className="grid gap-3 border-t border-line pt-4">
          <label className="grid gap-1 text-[13px]">
            Starts (leave empty for now)
            <input type="datetime-local" className="field min-h-9 px-2" value={effective} onChange={(e) => setEffective(e.target.value)} disabled={!!policy.scheduled} />
          </label>
          <label className="grid gap-1 text-[13px]">
            Why (optional)
            <input className="field min-h-9 px-2" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
          </label>
          <div className="flex items-center gap-3">
            <button className="btn btn-brand" onClick={save} disabled={busy || !!policy.scheduled}>Save as new version</button>
            {msg && <span role={msg.ok ? "status" : "alert"} className={`text-[13px] ${msg.ok ? "text-run" : "text-down"}`}>{msg.text}</span>}
          </div>
          {policy.scheduled && <p className="text-[12px] text-ink-3">A change is already scheduled; wait for it to start first.</p>}
        </div>
      ) : (
        <p className="text-[13px] text-ink-3">Only a factory admin can change policies.</p>
      )}
      {policy.history.length > 0 && (
        <details className="text-[13px]">
          <summary className="cursor-pointer text-ink-2">History ({policy.history.length})</summary>
          <ol className="mt-2 grid gap-1 font-mono text-[12px]">
            {policy.history.map((h) => (
              <li key={h.version}>v{h.version} · {when(h.effective_from)} → {h.effective_to ? when(h.effective_to) : "now"} · {JSON.stringify(h.body)}</li>
            ))}
          </ol>
        </details>
      )}
    </section>
  );
}

function ShiftForm({ policy, canEdit, onSaved }: { policy: Policy; canEdit: boolean; onSaved: () => void }) {
  const b = policy.current.body as { start: string; end: string; breaks: Break[] };
  const [start, setStart] = useState(b.start);
  const [end, setEnd] = useState(b.end);
  const [breaks, setBreaks] = useState<Break[]>(b.breaks ?? []);
  const crosses = toMin(end) <= toMin(start); // derived, so it can never disagree with the times
  const setBreak = (i: number, patch: Partial<Break>) => setBreaks((all) => all.map((x, n) => (n === i ? { ...x, ...patch } : x)));
  return (
    <Panel policy={policy} canEdit={canEdit} onSaved={onSaved} build={() => ({ start, end, crosses_midnight: crosses, breaks })}>
      <div className="flex flex-wrap items-end gap-4">
        <label className="grid gap-1 text-[13px]">Start<input type="time" className="field min-h-9 px-2" value={start} onChange={(e) => setStart(e.target.value)} disabled={!canEdit} /></label>
        <label className="grid gap-1 text-[13px]">End<input type="time" className="field min-h-9 px-2" value={end} onChange={(e) => setEnd(e.target.value)} disabled={!canEdit} /></label>
        {crosses && <span className="pb-2 text-[13px] text-ink-3">Ends the next day (night shift)</span>}
      </div>
      <fieldset className="grid gap-2">
        <legend className="mb-1 text-[13px] font-medium">Breaks</legend>
        {breaks.map((x, i) => (
          <div key={i} className="flex items-center gap-2">
            <input type="time" aria-label={`Break ${i + 1} start`} className="field min-h-9 px-2" value={x.start} onChange={(e) => setBreak(i, { start: e.target.value })} disabled={!canEdit} />
            <span>to</span>
            <input type="time" aria-label={`Break ${i + 1} end`} className="field min-h-9 px-2" value={x.end} onChange={(e) => setBreak(i, { end: e.target.value })} disabled={!canEdit} />
            {canEdit && <button type="button" className="btn btn-ghost btn-sm" onClick={() => setBreaks((all) => all.filter((_, n) => n !== i))}>Remove</button>}
          </div>
        ))}
        {canEdit && breaks.length < 6 && <button type="button" className="btn btn-sm w-fit" onClick={() => setBreaks((all) => [...all, { start: "12:00", end: "12:30" }])}>Add break</button>}
      </fieldset>
    </Panel>
  );
}

function NumbersForm({ policy, canEdit, onSaved, fields }: { policy: Policy; canEdit: boolean; onSaved: () => void; fields: { key: string; label: string; unit: string }[] }) {
  const [vals, setVals] = useState<Record<string, string>>(() => Object.fromEntries(fields.map((f) => [f.key, String(policy.current.body[f.key] ?? "")])));
  return (
    <Panel policy={policy} canEdit={canEdit} onSaved={onSaved} build={() => Object.fromEntries(fields.map((f) => [f.key, Number(vals[f.key])]))}>
      <div className="grid gap-3 sm:grid-cols-3">
        {fields.map((f) => (
          <label key={f.key} className="grid gap-1 text-[13px]">
            {f.label} ({f.unit})
            <input type="number" className="field min-h-9 px-2" value={vals[f.key]} onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })} disabled={!canEdit} />
          </label>
        ))}
      </div>
    </Panel>
  );
}

export default function PoliciesPage() {
  const me = useMe();
  const canEdit = hasRole(me, "factory_admin");
  const { data, error, loading, refresh } = useApi<Policy[]>("/policies");
  const by = (k: string) => data?.find((p) => p.kind === k);
  const shift = by("shift"), th = by("thresholds"), ret = by("retention");
  const key = (p: Policy) => `${p.kind}-${p.current.version}-${p.scheduled?.version ?? 0}`; // re-seed the form when a version changes

  return (
    <>
      <PageHeader title="Policies" sub="Each change is a new version. Reports and rankings use the version that was in force on the day." />
      {error && <ErrorBox message={error.message} onRetry={refresh} />}
      {loading && !data ? <Loading /> : (
        <div className="grid gap-4 xl:grid-cols-2">
          {shift && <ShiftForm key={key(shift)} policy={shift} canEdit={canEdit} onSaved={refresh} />}
          {th && <NumbersForm key={key(th)} policy={th} canEdit={canEdit} onSaved={refresh} fields={[
            { key: "target_efficiency_pct", label: "Target efficiency", unit: "%" },
            { key: "down_after_min", label: "Machine counts as down after", unit: "min" },
            { key: "idle_after_min", label: "Worker counts as idle after", unit: "min" },
          ]} />}
          {ret && <NumbersForm key={key(ret)} policy={ret} canEdit={canEdit} onSaved={refresh} fields={[
            { key: "events_days", label: "Keep activity events", unit: "days" },
            { key: "audit_days", label: "Keep audit log", unit: "days" },
          ]} />}
        </div>
      )}
    </>
  );
}
