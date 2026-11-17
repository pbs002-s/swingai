/** Stroke icon set drawn for StitchSense: one weight, one style. */

const PATHS = {
  logo: "",
  grid: "M3 3h6v6H3zM11 3h6v6h-6zM3 11h6v6H3zM11 11h6v6h-6z",
  floor: "M3 6h14M3 10h14M3 14h14M7 3v14M13 3v14",
  check: "M4 10.5 8 14l8-8",
  needle: "M5 16 15 4M13.5 3.5l3 3",
  alert: "M10 3 17 16H3zM10 8v3.5M10 13.6v.1",
  settings: "M10 7a3 3 0 1 1 0 6 3 3 0 0 1 0-6zM10 2v2.5M10 15.5V18M2 10h2.5M15.5 10H18M4.3 4.3l1.8 1.8M13.9 13.9l1.8 1.8M4.3 15.7l1.8-1.8M13.9 6.1l1.8-1.8",
  pulse: "M3 10h3l2-5 4 10 2-5h3",
  bars: "M4 16v-6M10 16V4M16 16V8",
  shield: "M10 3l6 3v5c0 3-3 5.5-6 6-3-.5-6-3-6-6V6z",
  server: "M4 4h12v5H4zM4 11h12v5H4zM7 6.5h.1M7 13.5h.1",
  camera: "M3 6h3l1.5-2h5L14 6h3v10H3zM10 8.5a3 3 0 1 1 0 6 3 3 0 0 1 0-6z",
  arrow: "M4 10h12M11 5l5 5-5 5",
  logout: "M8 4H4v12h4M12 7l3 3-3 3M15 10H8",
  sun: "M10 6.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7zM10 2v1.5M10 16.5V18M2 10h1.5M16.5 10H18",
  moon: "M15.5 12.5A6.5 6.5 0 0 1 7.5 4.5a6.5 6.5 0 1 0 8 8z",
  play: "M7 5l8 5-8 5z",
  pause: "M7 5v10M13 5v10",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18, className }: { name: IconName; size?: number; className?: string }) {
  if (name === "logo") return <Logo size={size} className={className} />;
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" aria-hidden="true" className={className}>
      <path d={PATHS[name]} stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Mark: a needle crossing a running stitch, inside a rounded square. */
export function Logo({ size = 26, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true" className={className}>
      <rect x="1" y="1" width="26" height="26" rx="8" fill="var(--ink)" />
      <path d="M9 21 19 7" stroke="var(--bg)" strokeWidth="2" strokeLinecap="round" />
      <circle cx="18" cy="8.5" r="1.5" stroke="var(--bg)" strokeWidth="1.2" />
      <path d="M5.5 16.5h3M11 16.5h3M16.5 16.5h3M22 16.5h1" stroke="var(--brand)" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
