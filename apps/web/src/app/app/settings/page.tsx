"use client";
import { T } from "@/lib/i18n";

import { useState } from "react";
import { ApiFailure, patch, post } from "@/lib/api";
import type { AlertRule } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { hasRole, useMe } from "@/components/app/Shell";
import { ErrorBox, Loading, PageHeader, SeverityMark } from "@/components/app/ui";

const NUMERIC_KEYS = ["min_minutes", "after_minutes", "lookback_minutes"];
const KEY_LABEL: Record<string, string> = { min_minutes: "after (min)", after_minutes: "after (min)", lookback_minutes: "look back (min)" };

function RuleRow({ rule, canEdit, onSaved }: { rule: AlertRule; canEdit: boolean; onSaved: () => void }) {
  const [draft, setDraft] = useState(rule);
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const [error, setError] = useState<string | null>(null);
  const [trial, setTrial] = useState<string | null>(null);
  const dirty = JSON.stringify(draft) !== JSON.stringify(rule);

  async function testRule() {
    setTrial("Testing…");
    setError(null);
    const condition = Object.fromEntries(Object.entries(draft.condition).filter(([k]) => NUMERIC_KEYS.includes(k)));
    try {
      const { data } = await post<{ would_raise: number | null; days: number; top_stations: { station: string; count: number }[]; note: string | null }>(
        `/alert-rules/${rule.id}/test`,
        { condition },
      );
      const top = data.top_stations.map((s) => `${s.station} ×${s.count}`).join(", ");
      setTrial(
        data.would_raise === null
          ? (data.note ?? "This rule cannot be replayed.")
          : `Would have raised ${data.would_raise} alert${data.would_raise === 1 ? "" : "s"} in the last ${data.days} days${top ? ` (most: ${top})` : ""}.`,
      );
    } catch (e) {
      setTrial(null);
      setError(e instanceof ApiFailure ? e.message : "Could not test.");
    }
  }

  async function save() {
    setState("saving");
    setError(null);
    const condition = Object.fromEntries(Object.entries(draft.condition).filter(([k]) => NUMERIC_KEYS.includes(k)));
    try {
      await patch(`/alert-rules/${rule.id}`, { is_enabled: draft.is_enabled, severity: draft.severity, condition });
      setState("saved");
      onSaved();
    } catch (e) {
      setError(e instanceof ApiFailure ? e.message : "Could not save.");
      setState("idle");
    }
  }

  const numeric = Object.entries(draft.condition).filter(([k]) => NUMERIC_KEYS.includes(k));
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line px-5 py-3.5 last:border-b-0">
      <SeverityMark level={draft.severity} />
      <div className="flex min-w-[200px] flex-1 flex-col">
        <span className="text-[14px] font-medium">{rule.name}</span>
        <span className="text-[12px] text-ink-3">Sent to {rule.recipient_roles.join(", ").replace(/_/g, " ")}</span>
      </div>
      {numeric.map(([k, v]) => (
        <label key={k} className="flex items-center gap-2 whitespace-nowrap text-[13px] text-ink-3">
          {KEY_LABEL[k] ?? k}
          <input
            type="number"
            min={1}
            max={600}
            disabled={!canEdit}
            value={Number(v)}
            onChange={(e) => setDraft({ ...draft, condition: { ...draft.condition, [k]: Number(e.target.value) } })}
            className="field w-20 min-h-9 px-2 text-right font-mono text-[14px]"
          />
        </label>
      ))}
      <label className="flex items-center gap-2 text-[13px] text-ink-3">
        Severity
        <select
          disabled={!canEdit}
          value={draft.severity}
          onChange={(e) => setDraft({ ...draft, severity: e.target.value as AlertRule["severity"] })}
          className="field min-h-9 w-[110px] px-2 text-[14px]"
        >
          <option value="critical"><T>Critical</T></option>
          <option value="warning"><T>Warning</T></option>
          <option value="info"><T>Info</T></option>
        </select>
      </label>
      <label className="flex min-h-9 cursor-pointer items-center gap-2 text-[13px]">
        <input type="checkbox" disabled={!canEdit} checked={draft.is_enabled} onChange={(e) => setDraft({ ...draft, is_enabled: e.target.checked })} className="size-4 accent-[var(--brand)]" />
        On
      </label>
      {canEdit && (
        <button type="button" className="btn btn-sm" onClick={testRule} aria-label={`Test ${rule.name} over the last 7 days`}>
          Test 7 days
        </button>
      )}
      {canEdit && (
        <button type="button" className="btn btn-brand btn-sm" disabled={!dirty || state === "saving"} onClick={save}>
          {state === "saving" ? "Saving…" : state === "saved" && !dirty ? "Saved" : "Save"}
        </button>
      )}
      {trial && <span role="status" className="w-full text-[13px] text-ink-2">{trial}</span>}
      {error && <span role="alert" className="w-full text-[13px] text-down">{error}</span>}
    </li>
  );
}

function SimulatorCard() {
  const sim = useApi<{ running: boolean }>("/simulator");
  const [error, setError] = useState<string | null>(null);
  async function toggle() {
    setError(null);
    try {
      await post("/simulator", { running: !sim.data?.running });
      void sim.refresh();
    } catch (e) {
      setError(e instanceof ApiFailure ? e.message : "Could not change the simulator.");
    }
  }
  return (
    <section aria-labelledby="sim-h" className="panel flex flex-wrap items-center gap-4 p-5">
      <div className="flex min-w-[240px] flex-1 flex-col gap-1">
        <h2 id="sim-h" className="text-[15px] font-semibold"><T>Factory simulator</T></h2>
        <p className="text-[13px] text-ink-3">Generates realistic station events for demos and training. Turn it off in a live factory.</p>
      </div>
      <span className={`rounded-md px-2 py-0.5 text-[12px] font-medium ${sim.data?.running ? "bg-run-bg text-run" : "bg-off-bg text-ink-2"}`}>
        {sim.data == null ? "…" : sim.data.running ? "Running" : "Stopped"}
      </span>
      <button type="button" className="btn btn-ghost btn-sm" onClick={toggle} disabled={sim.data == null}>
        {sim.data?.running ? "Stop simulator" : "Start simulator"}
      </button>
      {error && <span role="alert" className="w-full text-[13px] text-down">{error}</span>}
    </section>
  );
}

export default function SettingsPage() {
  const me = useMe();
  const canEdit = hasRole(me, "factory_admin");
  const rules = useApi<AlertRule[]>("/alert-rules");
  return (
    <>
      <PageHeader title="Settings" sub={canEdit ? "Alert rules apply to the whole factory. Every change is logged." : "Only a factory admin can change these."} />
      <div className="flex max-w-[1000px] flex-col gap-5">
        {canEdit && <SimulatorCard />}
        <section aria-labelledby="rules-h" className="panel overflow-hidden">
          <div className="border-b border-line px-5 py-3.5"><h2 id="rules-h" className="text-[15px] font-semibold"><T>Alert rules</T></h2></div>
          {rules.error && <div className="p-4"><ErrorBox message={rules.error.message} onRetry={rules.refresh} /></div>}
          {rules.loading && !rules.data ? <div className="p-4"><Loading /></div> : (
            <ul>{rules.data?.map((r) => <RuleRow key={r.id} rule={r} canEdit={canEdit} onSaved={rules.refresh} />)}</ul>
          )}
        </section>
      </div>
    </>
  );
}
