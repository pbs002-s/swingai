"use client";

import { useEffect, useState } from "react";

const FRAME_GAP_MS = 200;
const RETRY_MS = 1000;

/** Shows a browser-sourced test camera by re-fetching its newest JPEG (about 5 per second). */
export function FrameFeed({ url, alt }: { url: string; alt: string }) {
  const [n, setN] = useState(0);
  const [waiting, setWaiting] = useState(true);
  useEffect(() => () => setWaiting(true), [url]);
  const next = (ms: number) => setTimeout(() => setN((v) => v + 1), ms);
  return (
    <div className="relative size-full bg-black">
      {/* eslint-disable-next-line @next/next/no-img-element -- a changing JPEG, not a static asset */}
      <img
        src={`${url}?n=${n}`}
        alt={alt}
        className="size-full object-contain"
        onLoad={() => { setWaiting(false); next(FRAME_GAP_MS); }}
        onError={() => { setWaiting(true); next(RETRY_MS); }}
      />
      {waiting && <span className="absolute inset-0 grid place-items-center text-[13px] text-white/70">Waiting for the camera to send frames…</span>}
    </div>
  );
}
