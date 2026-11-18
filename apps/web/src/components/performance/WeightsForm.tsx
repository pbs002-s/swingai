"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { ApiFailure, post } from "@/lib/api";
import { T } from "@/lib/i18n";
import { COMPONENTS, LABEL } from "@/lib/types-performance";
import type { RankingPolicy, Weights } from "@/lib/types-performance";

export function WeightsForm({ policy, onSaved }: { policy: RankingPolicy; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Record<keyof Weights, string>>(() => toDraft(policy.weights));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const values = COMPONENTS.map((k) => Number(draft[k]));
  const sum = values.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0);
  const valid = values.every((v) => Number.isInteger(v) && v >= 0 && v <= 100) && sum === 100;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError(null);
    try {
      const weights = Object.fromEntries(COMPONENTS.map((k) => [k, Number(draft[k])]));
      const { data } = await post<RankingPolicy>("/performance/policy", { weights });
      setSaved(data.version);
      setOpen(false);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiFailure ? err.message : "Could not save the weights.");
    } finally {
      setBusy(false);
    }
  }

  if (!open)
    return (
      <div className="flex items-center gap-3">
        {saved != null && <span role="status" className="text-[13px] text-ink-3">Saved as version {saved}</span>}
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => {
            setDraft(toDraft(policy.weights));
            setOpen(true);
          }}
        >
          <T>Edit weights</T>
        </button>
      </div>
    );

  return (
    <form onSubmit={submit} aria-labelledby="weights-h" className="panel flex w-full flex-col gap-3 p-4">
      <h2 id="weights-h" className="text-[15px] font-semibold"><T>Ranking weights</T></h2>
      <div className="flex flex-wrap gap-3">
        {COMPONENTS.map((k) => (
          <label key={k} className="flex flex-col gap-1 text-[13px] text-ink-2">
            <T>{LABEL[k]}</T>
            <input
              className="field w-24 font-mono"
              type="number"
              inputMode="numeric"
              min={0}
              max={100}
              step={1}
              required
              value={draft[k]}
              onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
            />
          </label>
        ))}
      </div>
      <p aria-live="polite" className={`text-[13px] ${valid ? "text-ink-3" : "text-down"}`}>
        Total {sum} of 100{valid ? "" : ". Whole numbers that add up to exactly 100."}
      </p>
      {error && <p role="alert" className="text-[13px] text-down">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" className="btn btn-brand btn-sm" disabled={!valid || busy}>
          {busy ? "Saving…" : `Save as version ${policy.version + 1}`}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>
          <T>Cancel</T>
        </button>
      </div>
    </form>
  );
}

const toDraft = (w: Weights) => ({ production: String(w.production), quality: String(w.quality), time: String(w.time) });
