"use client";

import { useId, useState } from "react";
import type { Connection } from "@/lib/types-cameras";

export const STEPS = ["Edge box", "Find camera", "Test", "Assign stations", "Draw zones", "Settings", "Save and verify"] as const;

/** Only image data URLs are shown; anything else from an edge box is dropped. `<img>` never runs SVG scripts. */
export function safeSnapshot(src: string | null | undefined): string | null {
  return src && /^data:image\/(png|jpeg|webp|svg\+xml);base64,[A-Za-z0-9+/=]+$/.test(src) ? src : null;
}

export function StepIndicator({ current }: { current: number }) {
  return (
    <nav aria-label="Add camera steps" className="mb-6">
      <ol className="flex flex-wrap gap-2">
        {STEPS.map((label, i) => {
          const state = i < current ? "done" : i === current ? "current" : "todo";
          const tone =
            state === "current" ? "border-brand bg-brand-bg text-ink" : state === "done" ? "border-line text-ink-2" : "border-line text-ink-3";
          return (
            <li
              key={label}
              aria-current={state === "current" ? "step" : undefined}
              className={`flex min-h-11 items-center gap-2 rounded-xl border px-3 text-[13px] ${tone}`}
            >
              <span className="font-mono text-[12px]" aria-hidden="true">{state === "done" ? "✓" : i + 1}</span>
              <span>{label}</span>
              {state === "done" && <span className="sr-only">(done)</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: (id: string) => React.ReactNode }) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-medium">{label}</label>
      {children(id)}
      {hint && <span className="text-[12px] text-ink-3">{hint}</span>}
    </div>
  );
}

const HOST_RE = /^([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$|^[0-9a-fA-F:.]+$/;

export function connectionProblem(c: Connection): string | null {
  if (!HOST_RE.test(c.host)) return "Enter the camera's IP address or hostname.";
  if (!Number.isInteger(c.port) || c.port < 1 || c.port > 65535) return "Port must be between 1 and 65535.";
  if (!c.rtsp_path.startsWith("/") || /\s/.test(c.rtsp_path)) return "The RTSP path starts with / and has no spaces.";
  return null;
}

export function ConnectionForm({ value, onChange }: { value: Connection; onChange: (c: Connection) => void }) {
  const [showPassword, setShowPassword] = useState(false);
  const set = <K extends keyof Connection>(k: K, v: Connection[K]) => onChange({ ...value, [k]: v });
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="IP address or hostname">
        {(id) => <input id={id} className="field" value={value.host} onChange={(e) => set("host", e.target.value.trim())} placeholder="10.20.0.21" autoComplete="off" />}
      </Field>
      <Field label="RTSP port">
        {(id) => <input id={id} className="field" type="number" min={1} max={65535} value={value.port} onChange={(e) => set("port", Number(e.target.value))} />}
      </Field>
      <Field label="RTSP path" hint="From the camera's manual, for example /Streaming/Channels/101">
        {(id) => <input id={id} className="field font-mono" value={value.rtsp_path} onChange={(e) => set("rtsp_path", e.target.value.trim())} autoComplete="off" />}
      </Field>
      <Field label="Camera username">
        {(id) => <input id={id} className="field" value={value.username} onChange={(e) => set("username", e.target.value)} autoComplete="off" />}
      </Field>
      <Field label="Camera password" hint="Stored encrypted and sent only to the edge box. It is never shown again after saving.">
        {(id) => (
          <div className="flex gap-2">
            <input
              id={id}
              className="field flex-1"
              type={showPassword ? "text" : "password"}
              value={value.password}
              onChange={(e) => set("password", e.target.value)}
              autoComplete="new-password"
            />
            <button type="button" className="btn btn-ghost" aria-pressed={showPassword} onClick={() => setShowPassword((s) => !s)}>
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
        )}
      </Field>
    </div>
  );
}

export function Snapshot({ src, alt }: { src: string | null | undefined; alt: string }) {
  const safe = safeSnapshot(src);
  if (!safe) return <div className="grid aspect-video place-items-center rounded-xl bg-sunk text-[13px] text-ink-3">No snapshot</div>;
  // eslint-disable-next-line @next/next/no-img-element -- short-lived data URL from the edge box, not an optimisable asset
  return <img src={safe} alt={alt} className="aspect-video w-full rounded-xl border border-line object-cover" />;
}
