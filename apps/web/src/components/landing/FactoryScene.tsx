"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { draw, newWorld, step, viewBox } from "./factory-sim";
import type { World } from "./factory-sim";

type Props = { onStats?: (s: { made: number; packed: number; shipped: number }) => void; className?: string };

/** Animated isometric factory line. Pauses offscreen and when the tab is hidden; still frame under reduced motion. */
export function FactoryScene({ onStats, className }: Props) {
  const world = useRef<World | null>(null);
  const [, setFrame] = useState(0);
  const host = useRef<SVGSVGElement>(null);
  const vb = useMemo(viewBox, []);
  const statsCb = useRef(onStats);
  statsCb.current = onStats;

  if (world.current === null) {
    const w = newWorld();
    for (let i = 0; i < 12 * 30; i++) step(w, 1 / 30); // warm up: the first frame is already busy
    world.current = w;
  }

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;
    let raf = 0, last = 0, visible = true, lastStats = 0;
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting), { threshold: 0.05 });
    if (host.current) io.observe(host.current);
    const frame = (now: number) => {
      const dt = last ? Math.min((now - last) / 1000, 0.05) : 0;
      last = now;
      if (visible && !document.hidden && world.current) {
        step(world.current, dt);
        setFrame((f) => (f + 1) % 1_000_000);
        if (now - lastStats > 250) {
          lastStats = now;
          const { made, packed, shipped } = world.current;
          statsCb.current?.({ made, packed, shipped });
        }
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
    };
  }, []);

  const polys = draw(world.current);
  return (
    <svg
      ref={host}
      viewBox={vb}
      className={className}
      role="img"
      aria-label="Animated factory line: sewing machines make garments, a belt carries them to packing, cartons roll onto an export truck"
    >
      <g strokeLinejoin="round" strokeLinecap="round">
        {polys.map((p, i) =>
          p.fill === "none" ? (
            <polyline key={i} points={p.pts} fill="none" stroke={p.stroke ?? "var(--ink)"} strokeWidth={p.strokeWidth ?? 0.7} opacity={p.dim ? 0.35 : 0.85} />
          ) : (
            <polygon key={i} points={p.pts} fill={p.fill} stroke={p.stroke ?? "var(--ink)"} strokeWidth={p.strokeWidth ?? 0.7} strokeOpacity={p.dim ? 0.25 : 0.85} />
          ),
        )}
      </g>
    </svg>
  );
}
