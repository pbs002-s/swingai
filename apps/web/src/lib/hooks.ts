"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiFailure, api, isMockMode } from "@/lib/api";

type State<T> = { data: T | null; error: ApiFailure | null; loading: boolean };

/** Fetch `path`, refresh every `intervalMs` (0 = never) and whenever `refresh()` is called.
 *  Responses for an old `path` (or that arrive after a newer one) are dropped. */
export function useApi<T>(path: string | null, intervalMs = 0) {
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: true });
  const seq = useRef(0);
  const current = useRef(path);
  current.current = path;

  const load = useCallback(async () => {
    if (!path) return;
    const mine = ++seq.current;
    try {
      const { data } = await api<T>(path);
      if (mine === seq.current && current.current === path) setState({ data, error: null, loading: false });
    } catch (e) {
      if (mine === seq.current && current.current === path)
        setState((s) => ({ ...s, error: e instanceof ApiFailure ? e : new ApiFailure(0, "UNKNOWN", "Failed"), loading: false }));
    }
  }, [path]);

  useEffect(() => {
    setState((s) => ({ ...s, loading: true }));
    void load();
    if (!intervalMs) return () => void seq.current++;
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void load();
    }, intervalMs);
    return () => {
      // eslint-disable-next-line react-hooks/exhaustive-deps -- seq is a counter, not a DOM ref: bumping it marks in-flight loads stale
      seq.current++;
      window.clearInterval(id);
    };
  }, [load, intervalMs]);

  return { ...state, refresh: load };
}

/** Subscribe to the live event stream; `onEvent` fires for each named event. Reconnects on its own. */
export function useLiveStream(onEvent: (kind: string, data: Record<string, unknown>) => void, lineId?: number) {
  const handler = useRef(onEvent);
  handler.current = onEvent;
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (isMockMode()) return; // no live stream in the offline demo
    const url = `/api/v1/stream/floor${lineId ? `?line_id=${lineId}` : ""}`;
    const source = new EventSource(url, { withCredentials: true });
    const kinds = ["station_state", "alert", "alert_update", "review_added", "review_done"];
    const listeners = kinds.map((k) => {
      const fn = (e: MessageEvent) => {
        try {
          handler.current(k, JSON.parse(e.data));
        } catch {
          /* ignore malformed message */
        }
      };
      source.addEventListener(k, fn);
      return [k, fn] as const;
    });
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    return () => {
      listeners.forEach(([k, fn]) => source.removeEventListener(k, fn));
      source.close();
    };
  }, [lineId]);

  return connected;
}

/** Calls `fn` at most once per `ms`, trailing. */
export function useThrottled(fn: () => void, ms: number) {
  const timer = useRef<number | null>(null);
  const latest = useRef(fn);
  latest.current = fn;
  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = null;
    },
    [],
  );
  return useCallback(() => {
    if (timer.current) return;
    timer.current = window.setTimeout(() => {
      timer.current = null;
      latest.current();
    }, ms);
  }, [ms]);
}
