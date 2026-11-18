"use client";

import { useEffect, useRef } from "react";

/** Simulated feed for demo installs with no real camera: a moving sewing-table scene, clearly labelled. */
export function DemoFeed({ seed }: { seed: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    let raf = 0;
    let visible = false;
    const draw = (ms: number) => {
      const t = ms / 1000 + seed;
      const { width: w, height: h } = canvas;
      ctx.fillStyle = "#16181d";
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = "#23262d";
      ctx.fillRect(w * 0.1, h * 0.55, w * 0.8, h * 0.08); // table edge
      const wx = w * (0.5 + 0.03 * Math.sin(t * 0.7)); // worker torso sways
      ctx.fillStyle = "#3a3f4a";
      ctx.fillRect(wx - w * 0.09, h * 0.3, w * 0.18, h * 0.3);
      ctx.beginPath();
      ctx.arc(wx, h * 0.24, h * 0.09, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#6b7280";
      ctx.fillRect(wx + w * 0.1 + Math.sin(t * 9) * 3, h * 0.5, w * 0.12, h * 0.05); // fabric under the needle
      ctx.fillStyle = Math.sin(t * 9) > 0 ? "#e5e7eb" : "#9ca3af";
      ctx.fillRect(wx + w * 0.16, h * 0.38, 3, h * 0.14); // needle bar
      if (visible) raf = requestAnimationFrame(draw);
    };
    const watcher = new IntersectionObserver(([e]) => {  // only animate tiles on screen: 70+ cameras would otherwise all draw
      visible = e.isIntersecting;
      cancelAnimationFrame(raf);
      if (visible) raf = requestAnimationFrame(draw);
    });
    watcher.observe(canvas);
    return () => { watcher.disconnect(); cancelAnimationFrame(raf); };
  }, [seed]);
  return <canvas ref={ref} width={640} height={360} className="size-full object-cover" role="img" aria-label="Simulated camera feed" />;
}
