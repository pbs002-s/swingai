"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { ApiFailure, post } from "@/lib/api";

type Status = { kind: "idle" } | { kind: "sending" } | { kind: "sent" } | { kind: "error"; message: string };

export function LeadForm() {
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    if (!form.reportValidity()) return;
    const f = new FormData(form);
    setStatus({ kind: "sending" });
    try {
      await post("/leads", {
        name: String(f.get("name") ?? ""),
        email: String(f.get("email") ?? ""),
        company: String(f.get("company") ?? ""),
        stations: String(f.get("stations") ?? "under_100"),
        website: String(f.get("website") ?? ""),
      });
      setStatus({ kind: "sent" });
      form.reset();
    } catch (err) {
      setStatus({ kind: "error", message: err instanceof ApiFailure ? err.message : "Could not send. Try again." });
    }
  }

  if (status.kind === "sent") {
    return (
      <div role="status" className="panel flex flex-col gap-2 p-8">
        <span className="text-[20px] font-semibold tracking-[-0.02em]">Thanks. We will be in touch within two working days.</span>
        <span className="text-[15px] text-ink-2">We will ask about your machines, network and shift policies before the visit.</span>
      </div>
    );
  }

  const label = "flex flex-col gap-1.5 text-[14px] font-medium";
  return (
    <form onSubmit={handleSubmit} noValidate={false} className="grid grid-cols-1 gap-4 sm:grid-cols-2" aria-label="Book a site survey">
      <label className={label}>Your name<input className="field" name="name" autoComplete="name" required minLength={2} maxLength={120} /></label>
      <label className={label}>Work email<input className="field" name="email" type="email" autoComplete="email" required maxLength={254} /></label>
      <label className={label}>Factory or company<input className="field" name="company" autoComplete="organization" required minLength={2} maxLength={160} /></label>
      <label className={label}>
        Sewing stations
        <select className="field" name="stations" defaultValue="under_100">
          <option value="under_100">Under 100</option>
          <option value="100_500">100 to 500</option>
          <option value="over_500">Over 500</option>
        </select>
      </label>
      <label className="hidden" aria-hidden="true">Website<input name="website" tabIndex={-1} autoComplete="off" /></label>
      <div className="flex flex-wrap items-center gap-4 sm:col-span-2">
        <button type="submit" className="btn btn-primary" disabled={status.kind === "sending"}>
          {status.kind === "sending" ? "Sending…" : "Book a site survey"}
        </button>
        {status.kind === "error" && <span role="alert" className="text-[14px] text-down">{status.message}</span>}
      </div>
    </form>
  );
}
