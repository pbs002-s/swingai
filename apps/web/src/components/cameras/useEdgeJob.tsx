"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiFailure, api, post } from "@/lib/api";
import type { EdgeJob, JobKind } from "@/lib/types-cameras";

const POLL_MS = 1000;
const TIMEOUT_MS = 30_000;

export type JobPhase = "idle" | "waiting" | "done" | "failed" | "timeout";
type JobState<R> = { phase: JobPhase; job: EdgeJob<R> | null; error: string | null };

const message = (e: unknown) => (e instanceof ApiFailure ? e.message : "Something went wrong. Try again.");

/** Queue a job on an edge box and poll it every second until it finishes or 30 s pass. */
export function useEdgeJob<R>() {
  const [state, setState] = useState<JobState<R>>({ phase: "idle", job: null, error: null });
  const timer = useRef<number | null>(null);
  const runId = useRef(0);

  const stop = useCallback(() => {
    if (timer.current) window.clearInterval(timer.current);
    timer.current = null;
  }, []);
  useEffect(() => stop, [stop]);

  const run = useCallback(
    async (boxId: number, kind: JobKind, params: Record<string, unknown> = {}) => {
      stop();
      const mine = ++runId.current;
      const set = (s: JobState<R>) => mine === runId.current && setState(s);
      set({ phase: "waiting", job: null, error: null });
      let created: EdgeJob<R>;
      try {
        created = (await post<EdgeJob<R>>(`/edge-boxes/${boxId}/jobs`, { kind, params })).data;
      } catch (e) {
        set({ phase: "failed", job: null, error: message(e) });
        return;
      }
      const started = Date.now();
      timer.current = window.setInterval(async () => {
        if (Date.now() - started > TIMEOUT_MS) {
          stop();
          set({ phase: "timeout", job: created, error: "The edge box did not answer within 30 seconds. Check that it is online, then try again." });
          return;
        }
        try {
          const { data: job } = await api<EdgeJob<R>>(`/edge-boxes/${boxId}/jobs/${created.id}`);
          if (job.status === "done") {
            stop();
            set({ phase: "done", job, error: null });
          } else if (job.status === "failed") {
            stop();
            set({ phase: "failed", job, error: job.error ?? "The edge box could not finish this job." });
          }
        } catch {
          /* a dropped poll is retried on the next tick; the timeout reports a lasting failure */
        }
      }, POLL_MS);
    },
    [stop],
  );

  const reset = useCallback(() => {
    stop();
    runId.current++;
    setState({ phase: "idle", job: null, error: null });
  }, [stop]);

  return { ...state, run, reset };
}

export function JobProgress({ phase, label }: { phase: JobPhase; label: string }) {
  if (phase !== "waiting") return null;
  return (
    <p role="status" className="flex items-center gap-2 text-[14px] text-ink-2">
      <span className="size-3 animate-spin rounded-full border-2 border-line border-t-brand" aria-hidden="true" />
      {label}
    </p>
  );
}
