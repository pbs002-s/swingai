"use client";

import { useEffect, useState } from "react";
import { THEME_EVENT, currentTheme } from "@/components/ThemeToggle";
import type { Theme } from "@/components/ThemeToggle";

/** A quiet band with the hairline sewing-line figure: point at a station and it slides out of the line. */
export function SewingLine() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    setTheme(currentTheme());
    const onChange = (e: Event) => setTheme((e as CustomEvent<Theme>).detail);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onSystem = () => setTheme(currentTheme());
    window.addEventListener(THEME_EVENT, onChange);
    mq.addEventListener("change", onSystem);
    return () => {
      window.removeEventListener(THEME_EVENT, onChange);
      mq.removeEventListener("change", onSystem);
    };
  }, []);

  return (
    <section aria-labelledby="line-h" className="border-t border-line">
      <div className="mx-auto grid max-w-[1240px] grid-cols-1 items-center gap-10 px-6 py-20 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:py-24">
        <div data-reveal className="flex flex-col gap-4">
          <h2 id="line-h" className="text-[28px] font-semibold leading-[1.1] tracking-[-0.03em] sm:text-[34px]">
            Every station, one line on your screen
          </h2>
          <p className="max-w-[40ch] text-[16px] leading-[1.6] text-ink-2">
            Point at a machine. Its station steps forward with the needle down, the way a supervisor opens its timeline on the live floor.
          </p>
        </div>
        <div data-reveal className="relative mx-auto aspect-[400/320] w-full max-w-[560px]">
          {theme && (
            <iframe
              key={theme}
              src={`/hairline/sewing-line.html?theme=${theme}&play=1`}
              title="Interactive sewing line: point at a station to bring it forward"
              loading="lazy"
              className="absolute inset-0 h-full w-full border-0 bg-transparent"
            />
          )}
        </div>
      </div>
    </section>
  );
}
