"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Icon, Logo } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import type { IconName } from "@/components/Icon";
import { api, post } from "@/lib/api";
import type { Me } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n";

const DEMO = process.env.NEXT_PUBLIC_DEMO === "1";

// Who sees each page (system_admin sees all). The API enforces the same split; this only keeps the menu honest.
// `roles` omitted = every logged-in role.
type NavItem = { href: string; key: MessageKey; icon: IconName; roles?: string[] };
const NAV: NavItem[] = [
  { href: "/app", key: "overview", icon: "grid" },
  { href: "/app/floor", key: "liveFloor", icon: "floor", roles: ["factory_admin", "supervisor", "maintenance"] },
  { href: "/app/review", key: "reviewQueue", icon: "check", roles: ["factory_admin", "supervisor", "quality", "maintenance"] },
  { href: "/app/alerts", key: "alerts", icon: "alert", roles: ["factory_admin", "supervisor", "quality", "maintenance"] },
  { href: "/app/cameras/live", key: "liveCameras", icon: "play", roles: ["factory_admin", "supervisor", "management"] },
  { href: "/app/cameras", key: "cameras", icon: "camera", roles: ["factory_admin"] },
  { href: "/app/needles", key: "needles", icon: "needle", roles: ["factory_admin", "quality", "maintenance", "management"] },
  { href: "/app/performance", key: "performance", icon: "bars", roles: ["factory_admin", "management"] },
  { href: "/app/reports", key: "reports", icon: "check", roles: ["factory_admin", "management"] },
  { href: "/app/setup", key: "setup", icon: "server", roles: ["factory_admin"] },
  { href: "/app/settings", key: "settings", icon: "settings", roles: ["factory_admin"] },
  ...(DEMO ? [{ href: "/app/lab", key: "lab" as MessageKey, icon: "play" as IconName, roles: ["factory_admin"] }] : []),
];

const ROLE_LABEL: Record<string, string> = {
  system_admin: "System admin",
  factory_admin: "Factory admin",
  supervisor: "Supervisor",
  quality: "Quality",
  maintenance: "Maintenance",
  management: "Management",
};

const MeContext = createContext<Me | null>(null);
export const useMe = () => useContext(MeContext);
export const hasRole = (me: Me | null, ...roles: string[]) =>
  !!me?.roles.some((r) => r.role === "system_admin" || roles.includes(r.role));

const canSee = (me: Me | null, n: NavItem) => !n.roles || hasRole(me, ...n.roles);
const isActive = (n: NavItem, path: string) => (n.href === "/app" ? path === "/app" : path === n.href || path.startsWith(`${n.href}/`));

/** The menu item that owns this path: the longest matching href, so /app/cameras/live is not ruled by /app/cameras. */
function pageFor(path: string): NavItem | undefined {
  return NAV.filter((n) => isActive(n, path)).sort((a, b) => b.href.length - a.href.length)[0];
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { t, locale, setLocale } = useI18n();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    api<Me>("/auth/me").then(({ data }) => setMe(data)).catch(() => router.replace("/login"));
  }, [router]);

  async function logout() {
    try { await post("/auth/logout"); } finally { router.replace("/login"); }
  }

  if (!me) {
    return <div className="grid min-h-dvh place-items-center text-[14px] text-ink-3" role="status">{t("loading")}</div>;
  }

  return (
    <MeContext.Provider value={me}>
      <div className="flex min-h-dvh flex-col lg:flex-row">
        <aside className="print:hidden flex shrink-0 flex-col gap-4 border-b border-line bg-bg px-3 py-3 lg:sticky lg:top-0 lg:h-dvh lg:w-[232px] lg:border-b-0 lg:border-r lg:py-4">
          <div className="flex items-center justify-between gap-2 px-2">
            <Link href="/" className="flex items-center gap-2.5 text-ink" aria-label="StitchSense home">
              <Logo size={24} />
              <span className="text-[16px] font-semibold tracking-[-0.02em]">StitchSense</span>
            </Link>
          </div>
          <nav aria-label="App" className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
            {NAV.filter((n) => canSee(me, n)).map((n) => {
              const active = pageFor(pathname) === n;
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  aria-current={active ? "page" : undefined}
                  className={`flex min-h-10 shrink-0 items-center gap-2.5 rounded-lg px-3 text-[14px] transition-colors ${
                    active ? "bg-surface font-medium text-ink shadow-[0_0_0_1px_var(--line)]" : "text-ink-2 hover:bg-sunk hover:text-ink"
                  }`}
                >
                  <Icon name={n.icon} size={17} />
                  {t(n.key)}
                </Link>
              );
            })}
          </nav>
          <div className="mt-auto hidden flex-col gap-3 border-t border-line px-2 pt-3 lg:flex">
            <div className="flex items-center gap-2">
              <div role="group" aria-label="Language" className="flex overflow-hidden rounded-lg border border-line-2 text-[13px]">
                {(["en", "bn"] as const).map((l) => (
                  <button
                    key={l}
                    type="button"
                    aria-pressed={locale === l}
                    onClick={() => setLocale(l)}
                    className={`min-h-8 px-2.5 ${locale === l ? "bg-ink text-bg" : "text-ink-2 hover:bg-sunk"}`}
                  >
                    {l === "en" ? "EN" : "বাংলা"}
                  </button>
                ))}
              </div>
              <ThemeToggle />
            </div>
            <div className="flex items-center gap-2.5">
              <span className="grid size-8 place-items-center rounded-full bg-brand-bg text-[12px] font-semibold text-brand">
                {me.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-[13px] font-medium">{me.full_name}</span>
                <span className="truncate text-[12px] text-ink-3">{me.email}</span>
                <span className="truncate text-[12px] text-ink-3">{[...new Set(me.roles.map((r) => ROLE_LABEL[r.role] ?? r.role))].join(", ")}</span>
              </span>
              <button type="button" onClick={logout} className="btn btn-ghost btn-sm w-9 px-0" aria-label={t("logOut")}>
                <Icon name="logout" size={16} />
              </button>
            </div>
          </div>
        </aside>
        <main className="min-w-0 flex-1 px-4 py-5 sm:px-7 lg:py-6">
          {canSee(me, pageFor(pathname) ?? NAV[0]) ? children : (
            <div role="alert" className="panel max-w-xl p-6">
              <h1 className="text-[20px] font-semibold">{t("noAccess")}</h1>
              <p className="mt-1 text-[14px] text-ink-3">{t("noAccessText")}</p>
              <Link href="/app" className="btn mt-4">{t("overview")}</Link>
            </div>
          )}
        </main>
      </div>
    </MeContext.Provider>
  );
}
