"use client";

import { useState } from "react";
import { ApiFailure } from "@/lib/api";
import type { ImportKind, ImportResult } from "@/lib/types-setup";
import { Feedback, Section, Select, td, th, useAction } from "@/components/setup/shared";

const KINDS: { kind: ImportKind; label: string; template: string }[] = [
  { kind: "org", label: "Floors, lines and stations", template: "org_structure.csv" },
  { kind: "machines", label: "Machines", template: "machines.csv" },
  { kind: "workers", label: "Workers", template: "workers.csv" },
  { kind: "operations", label: "Products and operations", template: "operations.csv" },
  { kind: "needle-batches", label: "Needle batches", template: "needle_batches.csv" },
  { kind: "attendance", label: "Attendance punches", template: "attendance.csv" },
];

/** Multipart upload. lib/api's helper always sends JSON, so this posts the form itself (same CSRF header). */
async function upload(kind: ImportKind, file: File, commit: boolean): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  const csrf = document.cookie.match(/(?:^|;\s*)ss_csrf=([^;]+)/)?.[1] ?? "";
  let res: Response;
  try {
    res = await fetch(`/api/v1/import/${kind}?commit=${commit}`, {
      method: "POST",
      body: form,
      credentials: "same-origin",
      headers: { "x-csrf-token": decodeURIComponent(csrf) },
    });
  } catch {
    throw new ApiFailure(0, "NETWORK", "Cannot reach the server. Check the connection.");
  }
  const body = (await res.json().catch(() => null)) as { success: boolean; data: ImportResult; error: { code: string; message: string } | null } | null;
  if (!res.ok || !body?.success) throw new ApiFailure(res.status, body?.error?.code ?? "HTTP_ERROR", body?.error?.message ?? "Upload failed. Try again.");
  return body.data;
}

export function ImportTab() {
  const [kind, setKind] = useState<ImportKind>("org");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const act = useAction();
  const meta = KINDS.find((k) => k.kind === kind) ?? KINDS[0];

  async function send(commit: boolean) {
    if (!file) return;
    await act.run(
      async () => {
        const r = await upload(kind, file, commit);
        setResult(r);
        return r;
      },
      (r) => (r.committed ? `Imported: ${r.create} created, ${r.update} updated${r.error_count ? `, ${r.error_count} rows skipped` : ""}.` : "Preview ready. Nothing has been saved yet."),
    );
  }

  return (
    <Section title="Import from CSV" id="import-h">
      <div className="flex flex-col gap-4 px-5 py-4">
        <p className="max-w-[70ch] text-[13px] text-ink-3">
          Save the file as CSV UTF-8 with the template&apos;s header row. Preview checks every row first; Import then saves the valid rows in one go and skips rows with errors.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <Select label="What to import" value={kind} onChange={(v) => { setKind(v as ImportKind); setResult(null); }} className="w-60">
            {KINDS.map((k) => <option key={k.kind} value={k.kind}>{k.label}</option>)}
          </Select>
          <label className="flex flex-col gap-1 text-[13px] text-ink-2">
            CSV file
            <input
              type="file"
              accept=".csv,text/csv"
              className="field flex min-h-11 items-center py-2"
              onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); }}
            />
          </label>
          <button type="button" className="btn btn-ghost btn-sm min-h-11" disabled={!file || act.busy} onClick={() => void send(false)}>Preview</button>
          <button
            type="button"
            className="btn btn-brand btn-sm min-h-11"
            disabled={!file || act.busy || !result || result.committed || result.create + result.update === 0}
            onClick={() => void send(true)}
          >
            Import valid rows
          </button>
          <a className="btn btn-ghost btn-sm min-h-11" href={`/templates/${meta.template}`} download>Download template</a>
        </div>
        <Feedback msg={act.msg} />
        {result && (
          <div className="flex flex-col gap-3" aria-live="polite">
            <dl className="flex flex-wrap gap-6 text-[14px]">
              <div><dt className="text-[12px] text-ink-3">To create</dt><dd className="font-mono text-[20px]">{result.create}</dd></div>
              <div><dt className="text-[12px] text-ink-3">To update</dt><dd className="font-mono text-[20px]">{result.update}</dd></div>
              <div><dt className="text-[12px] text-ink-3">Rows with errors</dt><dd className={`font-mono text-[20px] ${result.error_count ? "text-down" : ""}`}>{result.error_count}</dd></div>
            </dl>
            {result.errors.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-line">
                <table className="w-full min-w-[480px] border-collapse text-[14px]" aria-label="Row errors">
                  <thead><tr><th className={th}>Row</th><th className={th}>Column</th><th className={th}>Problem</th></tr></thead>
                  <tbody>
                    {result.errors.map((e, i) => (
                      <tr key={`${e.row}-${i}`}>
                        <td className={`${td} font-mono`}>{e.row}</td>
                        <td className={`${td} font-mono`}>{e.column || "—"}</td>
                        <td className={td}>{e.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {result.error_count > result.errors.length && (
                  <p className="px-4 py-2 text-[13px] text-ink-3">Showing the first {result.errors.length} of {result.error_count} errors.</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </Section>
  );
}
