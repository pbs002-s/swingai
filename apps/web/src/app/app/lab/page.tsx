"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ObjectDetector } from "@mediapipe/tasks-vision";
import { ApiFailure, api, post } from "@/lib/api";
import { PageHeader } from "@/components/app/ui";
import { motion, newTracker, step } from "@/components/lab/activity";
import type { Tracker } from "@/components/lab/activity";
import { best, detect, loadDetector } from "@/components/lab/detector";
import type { Box } from "@/components/lab/detector";
import { ResultsPanel } from "@/components/lab/ResultsPanel";

const TICK_MS = 200; // 5 frames per second, like the edge pipeline
const FRAME_WIDTH = 640;
const JPEG_QUALITY = 0.6;
const MOTION_W = 64;
const MOTION_H = 36;

type Status = "idle" | "starting" | "live";

function drawBoxes(canvas: HTMLCanvasElement | null, video: HTMLVideoElement, boxes: Box[]) {
  const ctx = canvas?.getContext("2d");
  if (!canvas || !ctx) return;
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  ctx.lineWidth = 3;
  ctx.font = "16px sans-serif";
  for (const b of boxes) {
    ctx.strokeStyle = ctx.fillStyle = b.label === "person" ? "#22c55e" : "#ef4444";
    ctx.strokeRect(b.x, b.y, b.w, b.h);
    ctx.fillText(`${b.label === "person" ? "person" : "phone"} ${Math.round(b.score * 100)}%`, b.x + 4, b.y + 18);
  }
}

export default function LabPage() {
  const video = useRef<HTMLVideoElement>(null);
  const overlay = useRef<HTMLCanvasElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const detector = useRef<ObjectDetector | null>(null);
  const cameraId = useRef<number | null>(null);
  const [name, setName] = useState("Lab test camera");
  const [share, setShare] = useState(true);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [tracker, setTracker] = useState<Tracker | null>(null);
  const [analysis, setAnalysis] = useState("Start the camera to analyse.");

  const stop = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    timer.current = null;
    stream.current = null;
    setStatus("idle");
  }, []);
  useEffect(() => stop, [stop]);
  useEffect(() => () => detector.current?.close(), []);

  function startLoop(id: number | null) {
    const shot = document.createElement("canvas");
    const small = document.createElement("canvas");
    small.width = MOTION_W;
    small.height = MOTION_H;
    let prevGray: Uint8ClampedArray | null = null;
    let tr: Tracker | null = null;
    let sending = false;

    timer.current = setInterval(() => {
      const v = video.current;
      if (!v || !v.videoWidth) return;
      if (detector.current) {
        const boxes = detect(detector.current, v, performance.now());
        const sctx = small.getContext("2d", { willReadFrequently: true });
        sctx?.drawImage(v, 0, 0, MOTION_W, MOTION_H);
        const m = motion(prevGray, sctx?.getImageData(0, 0, MOTION_W, MOTION_H).data ?? new Uint8ClampedArray());
        prevGray = m.gray;
        const t = performance.now() / 1000;
        tr = step(tr ?? newTracker(t), { t, person: best(boxes, "person"), phone: best(boxes, "cell phone"), motion: m.score });
        setTracker(tr);
        drawBoxes(overlay.current, v, boxes);
      }
      if (id === null || sending) return;
      sending = true;
      shot.width = FRAME_WIDTH;
      shot.height = Math.round((FRAME_WIDTH * v.videoHeight) / v.videoWidth);
      shot.getContext("2d")?.drawImage(v, 0, 0, shot.width, shot.height);
      const jpeg = shot.toDataURL("image/jpeg", JPEG_QUALITY).split(",")[1];
      api(`/cameras/${id}/frame`, { method: "PUT", body: JSON.stringify({ jpeg }) })
        .catch((e) => { if (e instanceof ApiFailure && e.status !== 0) setError(`Live view stopped: ${e.message}`); })
        .finally(() => { sending = false; });
    }, TICK_MS);
  }

  async function start() {
    setError(null);
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setError("This browser blocks the camera on plain http. Open this page on localhost, or over https (a phone on the lab network needs https).");
      return;
    }
    setStatus("starting");
    try {
      const media = await navigator.mediaDevices.getUserMedia({ video: true, audio: false }); // no audio, ever
      stream.current = media;
      if (video.current) { video.current.srcObject = media; await video.current.play(); }
      if (share && cameraId.current === null) {
        cameraId.current = (await post<{ id: number }>("/cameras/test-source", { name: name.trim() || "Lab test camera" })).data.id;
      }
      startLoop(share ? cameraId.current : null);
      setStatus("live");
    } catch (e) {
      stop();
      setError(e instanceof ApiFailure ? e.message : "Could not open the camera. Allow camera access and try again.");
      return;
    }
    if (!detector.current) {
      setAnalysis("Loading the detection model (about 5 MB, first time only)…");
      try {
        detector.current = await loadDetector();
        setAnalysis("Analysing…");
      } catch {
        setAnalysis("The detection model could not load (needs internet the first time). Live view still works.");
      }
    }
  }

  return (
    <>
      <PageHeader
        title="Lab"
        sub="Test area. Nothing here is saved or counted toward anyone's numbers. Not available in production."
        actions={<Link href="/app/cameras/live" className="btn">Open live cameras</Link>}
      />
      <p className="mb-4 rounded-lg border border-idle/60 bg-idle-bg px-3 py-2 text-[13px] text-idle">
        Analysis runs in this browser. Faces are not blurred in the live view and privacy zones are not applied, so use it only with people who agreed to the test.
      </p>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <section aria-labelledby="cam-h" className="panel grid content-start gap-4 p-5">
          <h2 id="cam-h" className="text-[16px] font-semibold">Camera</h2>
          <div className="flex flex-wrap items-end gap-4">
            <label className="grid gap-1 text-[14px]">
              Camera name
              <input className="field min-h-9 px-2" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} disabled={status !== "idle" || cameraId.current !== null} />
            </label>
            <label className="flex min-h-9 items-center gap-2 text-[14px]">
              <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} disabled={status !== "idle"} />
              Also show in Live cameras
            </label>
          </div>
          <div className="relative aspect-video overflow-hidden rounded-xl border border-line bg-black">
            <video ref={video} muted playsInline className="size-full object-contain" aria-label="Camera preview" />
            <canvas ref={overlay} className="pointer-events-none absolute inset-0 size-full object-contain" aria-hidden="true" />
          </div>
          {error && <p role="alert" className="text-[14px] text-down">{error}</p>}
          <div className="flex items-center gap-3">
            {status === "idle" ? (
              <button className="btn btn-brand" onClick={start}>Start camera</button>
            ) : (
              <button className="btn" onClick={stop} disabled={status === "starting"}>Stop</button>
            )}
            <span className="text-[13px] text-ink-3" role="status">
              {status === "live" ? (share ? "Live, also in Live cameras" : "Live, this browser only") : status === "starting" ? "Starting…" : "Stopped"}
            </span>
          </div>
        </section>
        <section aria-labelledby="res-h" className="panel grid content-start gap-4 p-5">
          <h2 id="res-h" className="text-[16px] font-semibold">What the camera sees</h2>
          <ResultsPanel tracker={tracker} status={analysis} />
        </section>
      </div>
    </>
  );
}
