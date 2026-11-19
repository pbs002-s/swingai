"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { DemoFeed } from "@/components/cameras/DemoFeed";
import { FrameFeed } from "@/components/cameras/FrameFeed";

export type LiveCamera = {
  id: number;
  code: string;
  name: string;
  stations: { id: number; code: string }[];
  online: boolean;
  privacy_zones: number;
  live: { mode: "embed" | "demo" | "frames" | "none"; url: string | null };
};

const ROTATE_MS = 10_000;
const label = (c: LiveCamera) => (c.stations.length ? `${c.name} · ${c.stations.map((s) => s.code).join(", ")}` : c.name);

export function Feed({ cam }: { cam: LiveCamera }) {
  if (cam.live.mode === "embed" && cam.live.url) {
    return <iframe src={cam.live.url} title={label(cam)} allow="autoplay; fullscreen" className="size-full border-0 bg-black" />;
  }
  if (cam.live.mode === "frames" && cam.live.url) return <FrameFeed url={cam.live.url} alt={label(cam)} />;
  if (cam.live.mode === "demo") return <DemoFeed seed={cam.id} />;
  return (
    <div className="grid size-full place-items-center bg-sunk px-4 text-center text-[13px] text-ink-3">
      No live view yet. Set the edge box live address to watch this camera.
    </div>
  );
}

export function Tile({ cam, onOpen }: { cam: LiveCamera; onOpen: () => void }) {
  return (
    <button type="button" onClick={onOpen} aria-label={`Open ${label(cam)} full screen`} className="group relative aspect-video overflow-hidden rounded-xl border border-line bg-black text-left">
      <div className="pointer-events-none size-full"><Feed cam={cam} /></div>
      <span className="absolute inset-x-0 bottom-0 flex items-center gap-2 bg-gradient-to-t from-black/80 to-transparent px-3 py-2 text-[13px] text-white">
        <span className={`size-2 rounded-full ${cam.online ? "bg-run" : "border border-off"}`} aria-hidden="true" />
        {label(cam)}
        {(cam.live.mode === "demo" || cam.live.mode === "frames") && (
          <span className="ml-auto rounded bg-white/20 px-1.5 text-[11px]">{cam.live.mode === "demo" ? "Simulated" : "Test camera"}</span>
        )}
        {cam.live.mode === "embed" && cam.privacy_zones === 0 && (
          <span className="rounded bg-idle-bg px-1.5 text-[11px] text-idle" title="No privacy zone is drawn for this camera, so the whole picture is shown.">
            No privacy mask
          </span>
        )}
        {!cam.online && cam.live.mode === "embed" && <span className="ml-auto text-[11px]">Offline</span>}
      </span>
    </button>
  );
}

/** Full-screen viewer: arrow keys / buttons change camera, Esc leaves, Rotate cycles every 10 s. */
export function Viewer({ cams, start, onClose }: { cams: LiveCamera[]; start: number; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const [i, setI] = useState(start);
  const [rotate, setRotate] = useState(false);
  const step = useCallback((d: number) => setI((n) => (n + d + cams.length) % cams.length), [cams.length]);

  useEffect(() => {
    const el = box.current;
    void el?.requestFullscreen?.().catch(() => undefined); // if refused, the overlay still fills the window
    const onFs = () => { if (!document.fullscreenElement) onClose(); };
    document.addEventListener("fullscreenchange", onFs);
    return () => {
      document.removeEventListener("fullscreenchange", onFs);
      if (document.fullscreenElement) void document.exitFullscreen();
    };
  }, [onClose]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") step(1);
      else if (e.key === "ArrowLeft") step(-1);
      else if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, onClose]);

  useEffect(() => {
    if (!rotate) return;
    const id = setInterval(() => step(1), ROTATE_MS);
    return () => clearInterval(id);
  }, [rotate, step]);

  const cam = cams[i];
  return (
    <div ref={box} role="dialog" aria-modal="true" aria-label={label(cam)} className="fixed inset-0 z-50 flex flex-col bg-black text-white">
      <div className="min-h-0 flex-1"><Feed cam={cam} /></div>
      <div className="flex flex-wrap items-center gap-2 bg-black/90 px-4 py-3 text-[14px]">
        <span className="font-medium">{label(cam)}</span>
        <span className="text-white/60">{i + 1} / {cams.length}</span>
        <span className="ml-auto flex gap-2">
          <button className="btn" onClick={() => step(-1)} aria-label="Previous camera">‹ Prev</button>
          <button className="btn" onClick={() => step(1)} aria-label="Next camera">Next ›</button>
          <button className="btn" onClick={() => setRotate((r) => !r)} aria-pressed={rotate}>{rotate ? "Stop rotate" : "Rotate"}</button>
          <button className="btn btn-brand" onClick={onClose}>Exit</button>
        </span>
      </div>
    </div>
  );
}
