"use client";

import Link from "next/link";
import { useRef } from "react";
import { Logo } from "@/components/Icon";
import { Hero } from "./Hero";
import { LeadForm } from "./LeadForm";
import { useLandingMotion } from "./motion";
import { FairUse, HowItWorks, Install, NeedleTracing } from "./Sections";

const NAV = [
  ["#how", "How it works"],
  ["#needles", "Needle tracing"],
  ["#fair", "Fair use"],
  ["#install", "Installation"],
] as const;

export function Landing() {
  const root = useRef<HTMLDivElement>(null);
  useLandingMotion(root);

  return (
    <div ref={root} className="relative">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-ink focus:px-4 focus:py-2 focus:text-bg">
        Skip to content
      </a>

      {/* the seam: a running stitch that sews itself down the page as you scroll */}
      <div aria-hidden="true" className="pointer-events-none absolute bottom-0 left-[max(12px,calc((100vw-1240px)/2-28px))] top-0 z-0 hidden w-[2px] xl:block">
        <div
          data-seam
          className="h-full w-full origin-top"
          style={{ backgroundImage: "repeating-linear-gradient(to bottom, var(--brand) 0 9px, transparent 9px 16px)", opacity: 0.55 }}
        />
      </div>

      <header className="sticky top-0 z-40 border-b border-line/70 bg-bg/80 backdrop-blur-md">
        <nav aria-label="Main" className="mx-auto flex max-w-[1240px] items-center gap-8 px-6 py-3">
          <Link href="/" className="flex items-center gap-2.5 text-ink" aria-label="StitchSense home">
            <Logo size={26} />
            <span className="text-[17px] font-semibold tracking-[-0.02em]">StitchSense</span>
          </Link>
          <div className="hidden flex-1 items-center gap-7 text-[14px] text-ink-2 md:flex">
            {NAV.map(([href, label]) => (
              <a key={href} href={href} className="link-draw py-2 transition-colors hover:text-ink">{label}</a>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Link href="/login" className="btn btn-ghost btn-sm">Log in</Link>
            <a href="#contact" className="btn btn-primary btn-sm hidden sm:inline-flex">Book a site survey</a>
          </div>
        </nav>
      </header>

      <main id="main" className="relative z-10">
        <Hero />
        <HowItWorks />
        <NeedleTracing />
        <FairUse />
        <Install />
        <section id="contact" className="border-t border-line bg-surface">
          <div className="mx-auto grid max-w-[1240px] grid-cols-1 gap-14 px-6 py-24 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:py-32">
            <div data-reveal className="flex flex-col gap-5">
              <h2 className="text-[38px] font-semibold leading-[1.04] tracking-[-0.035em] sm:text-[52px]">Start with one line of ten stations</h2>
              <p className="max-w-[42ch] text-[17px] leading-[1.6] text-ink-2">
                We visit the floor, check your machines and network, and run a pilot in observation mode next to your current records before anything goes live.
              </p>
            </div>
            <div data-reveal>
              <LeadForm />
            </div>
          </div>
        </section>
      </main>

      <footer className="relative z-10 border-t border-line">
        <div className="mx-auto flex max-w-[1240px] flex-wrap items-center gap-x-8 gap-y-3 px-6 py-8 text-[14px] text-ink-3">
          <span className="flex items-center gap-2 font-semibold text-ink"><Logo size={20} />StitchSense</span>
          <a href="#fair" className="link-draw">Worker privacy</a>
          <a href="#install" className="link-draw">Deployment</a>
          <Link href="/login" className="link-draw">Log in</Link>
          <span className="ml-auto">© {new Date().getFullYear()} StitchSense</span>
        </div>
      </footer>
    </div>
  );
}
