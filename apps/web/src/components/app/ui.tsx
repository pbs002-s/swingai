"use client";

import type { ReactNode } from "react";
import type { TileState } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n";

export const STATE_META: Record<TileState, { key: MessageKey; tile: string; swatch: string; mark: string }> = {
  running: { key: "running", tile: "bg-run-bg text-run border-run/60", swatch: "bg-run", mark: "" },
  idle: { key: "idle", tile: "bg-idle-bg text-idle border-idle/70", swatch: "bg-idle-bg border border-idle", mark: "▲" },
  down: { key: "down", tile: "bg-down text-white border-down", swatch: "bg-down", mark: "✕" },
  break: { key: "break", tile: "bg-sunk text-ink-2 border-line-2", swatch: "bg-sunk border border-line-2", mark: "" },
  no_data: { key: "noData", tile: "bg-off-bg text-ink-2 border-dashed border-off", swatch: "bg-off-bg border border-dashed border-off", mark: "?" },
};

export const SEVERITY = {
  critical: { shape: "M9 1 17 9 9 17 1 9Z", color: "var(--down)", label: "Critical" },
  warning: { shape: "M9 2 17 16H1Z", color: "var(--idle)", label: "Warning" },
  info: { shape: "M9 2a7 7 0 1 1 0 14A7 7 0 0 1 9 2Z", color: "var(--off)", label: "Info" },
} as const;

export function SeverityMark({ level }: { level: keyof typeof SEVERITY }) {
  const s = SEVERITY[level];
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" role="img" aria-label={s.label} className="shrink-0">
      <path d={s.shape} fill={s.color} />
    </svg>
  );
}

export function PageHeader({ title, sub, actions }: { title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end gap-x-6 gap-y-3">
      <div className="flex flex-col gap-1">
        <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.03em]">{title}</h1>
        {sub && <p className="text-[14px] text-ink-3">{sub}</p>}
      </div>
      {actions && <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Legend() {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-ink-3">
      {(Object.keys(STATE_META) as TileState[]).map((s) => (
        <span key={s} className="flex items-center gap-1.5">
          <span className={`size-2.5 rounded-[3px] ${STATE_META[s].swatch}`} />
          {t(STATE_META[s].key)}
        </span>
      ))}
    </div>
  );
}

export function Loading() {
  const { t } = useI18n();
  return (
    <div role="status" className="grid gap-3">
      <span className="sr-only">{t("loading")}</span>
      {[0, 1, 2].map((i) => <div key={i} className="h-24 animate-pulse rounded-2xl bg-sunk" />)}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-down/30 bg-down-bg px-4 py-3 text-[14px] text-down">
      {message}
      {onRetry && <button type="button" className="btn btn-ghost btn-sm ml-auto" onClick={onRetry}>{t("retry")}</button>}
    </div>
  );
}

export function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="flex flex-col items-center gap-1 px-6 py-12 text-center">
      <span className="text-[15px] font-medium">{title}</span>
      <span className="max-w-[40ch] text-[14px] text-ink-3">{text}</span>
    </div>
  );
}

export function LiveDot({ on }: { on: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] text-ink-3">
      <span className={`size-1.5 rounded-full ${on ? "bg-run" : "bg-off"}`} />
      {on ? "live" : "reconnecting"}
    </span>
  );
}

export const fmtTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";

export function minutesSince(iso: string | null): string {
  if (!iso) return "";
  const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

export const pct = (v: number | null | undefined) => (v == null ? "—" : `${v.toFixed(1)}%`);
export const num = (v: number) => v.toLocaleString("en-US");
