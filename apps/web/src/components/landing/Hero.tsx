"use client";

import Link from "next/link";
import { useState } from "react";
import { DEFAULT_CLOTH, setCloth } from "./factory-sim";
import { FactoryScene } from "./FactoryScene";

function Counter({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col">
      <span className="font-mono text-[22px] font-medium tabular tracking-tight text-ink">{value.toLocaleString("en-US")}</span>
      <span className="text-[13px] text-ink-3">{label}</span>
    </div>
  );
}

function ClothColours() {
  const [colors, setColors] = useState<string[]>(DEFAULT_CLOTH);
  const change = (i: number, value: string) => {
    const next = colors.map((c, k) => (k === i ? value : c));
    setColors(next);
    setCloth(next);
  };
  return (
    <div className="flex items-center gap-2 px-3 pt-3">
      <span className="text-[12px] text-ink-3">Cloth colours</span>
      <div role="group" aria-label="Cloth colours" className="flex gap-1.5">
        {colors.map((c, i) => (
          <label key={i} className="relative grid size-7 cursor-pointer place-items-center rounded-full transition-transform hover:scale-110">
            <span className="size-5 rounded-full ring-1 ring-line-2" style={{ background: c }} />
            <input type="color" value={c} onChange={(e) => change(i, e.target.value)} aria-label={`Cloth colour ${i + 1}`} className="absolute inset-0 cursor-pointer opacity-0" />
          </label>
        ))}
      </div>
      <button type="button" className="link-draw ml-auto text-[12px] text-ink-3 hover:text-ink" onClick={() => { setColors(DEFAULT_CLOTH); setCloth(DEFAULT_CLOTH); }}>
        Reset
      </button>
    </div>
  );
}

export function Hero() {
  const [stats, setStats] = useState({ made: 0, packed: 0, shipped: 0 });
  return (
    <section className="relative overflow-hidden">
      <div aria-hidden="true" className="weave pointer-events-none absolute inset-0 opacity-70" />
      <div className="relative mx-auto grid max-w-[1240px] grid-cols-1 items-center gap-12 px-6 pb-20 pt-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)] lg:pt-24">
        <div className="flex flex-col gap-7">
          <h1 data-split className="text-[44px] font-semibold leading-[1.02] tracking-[-0.035em] text-ink sm:text-[60px] lg:text-[68px]">
            Sewing-floor monitoring for garment factories
          </h1>
          <p data-hero-fade className="max-w-[34ch] text-[18px] leading-[1.55] text-ink-2">
            Working time, output against target and needle breaks for every station, on one screen your supervisors can trust.
          </p>
          <div data-hero-fade className="flex flex-wrap gap-3">
            <a href="#contact" className="btn btn-primary">Book a site survey</a>
            <Link href="/login" className="btn btn-ghost">Open the live demo</Link>
          </div>
          <p data-hero-fade className="flex items-center gap-2.5 text-[14px] text-ink-3">
            <span className="relative flex size-2" aria-hidden="true">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-run opacity-60" />
              <span className="relative inline-flex size-2 rounded-full bg-run" />
            </span>
            Runs on your own server. Works with any machine brand.
          </p>
        </div>

        <div data-hero-fade className="relative">
          <div className="relative rounded-[22px] border border-line bg-surface p-3 shadow-[0_30px_60px_-30px_rgb(20_22_25/0.35),0_2px_6px_rgb(20_22_25/0.05)]">
            <div className="flex items-center gap-2 px-2 pb-2 text-[12px] text-ink-3">
              <span className="size-2.5 rounded-full bg-line-2" />
              <span className="size-2.5 rounded-full bg-line-2" />
              <span className="size-2.5 rounded-full bg-line-2" />
              <span className="ml-2 font-mono">line-3 · simulation</span>
            </div>
            <div className="overflow-hidden rounded-[14px] bg-bg">
              <FactoryScene onStats={setStats} className="block h-auto w-full" />
            </div>
            <ClothColours />
            <div className="grid grid-cols-3 gap-4 border-t border-line px-3 pt-3 mt-2">
              <Counter value={stats.made} label="garments sewn" />
              <Counter value={stats.packed} label="cartons packed" />
              <Counter value={stats.shipped} label="trucks shipped" />
            </div>
          </div>
          <div aria-hidden="true" className="float-a absolute -right-4 top-14 hidden rounded-xl border border-line bg-surface/95 px-3 py-2 text-[12px] shadow-lg backdrop-blur sm:block">
            <span className="flex items-center gap-2 font-medium text-ink"><span className="size-2 rotate-45 bg-down" />Machine stopped 12 min</span>
            <span className="font-mono text-ink-3">L3-S12 · 09:30</span>
          </div>
          <div aria-hidden="true" className="float-b absolute -left-6 bottom-24 hidden rounded-xl border border-line bg-surface/95 px-3 py-2 text-[12px] shadow-lg backdrop-blur sm:block">
            <span className="flex items-center gap-2 font-medium text-ink"><span className="size-0 border-x-[5px] border-b-[9px] border-x-transparent border-b-idle" />Possible phone use</span>
            <span className="font-mono text-ink-3">0.87 · waiting for review</span>
          </div>
        </div>
      </div>
    </section>
  );
}
