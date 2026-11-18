"use client";

import { Suspense } from "react";
import type { KeyboardEvent } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { hasRole, useMe } from "@/components/app/Shell";
import { Loading, PageHeader } from "@/components/app/ui";
import { ImportTab } from "@/components/setup/ImportTab";
import { ListsTab } from "@/components/setup/ListsTab";
import { MachinesTab } from "@/components/setup/MachinesTab";
import { StructureTab } from "@/components/setup/StructureTab";
import { UsersTab } from "@/components/setup/UsersTab";
import { WorkersTab } from "@/components/setup/WorkersTab";

const TABS = [
  { id: "structure", label: "Structure" },
  { id: "machines", label: "Machines" },
  { id: "lists", label: "Lists" },
  { id: "workers", label: "Workers" },
  { id: "users", label: "Users", sysadmin: true },
  { id: "import", label: "Import", admin: true },
] as const;
type TabId = (typeof TABS)[number]["id"];

function SetupHub() {
  const me = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const canEdit = hasRole(me, "factory_admin");
  const isSysadmin = !!me?.roles.some((r) => r.role === "system_admin");
  const tabs = TABS.filter((t) => (!("sysadmin" in t) || isSysadmin) && (!("admin" in t) || canEdit));
  const tab: TabId = tabs.find((t) => t.id === params.get("tab"))?.id ?? "structure";

  const go = (id: TabId) => router.replace(`${pathname}?tab=${id}`, { scroll: false });
  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    const i = tabs.findIndex((t) => t.id === tab);
    const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
    if (next === null) return;
    const t = tabs[(next + tabs.length) % tabs.length];
    go(t.id);
    document.getElementById(`tab-${t.id}`)?.focus();
  }

  return (
    <>
      <PageHeader
        title="Setup"
        sub={canEdit ? "Factory structure, machines, lists, people and imports. Every change is logged." : "Read only. Only a factory admin can change setup."}
      />
      <div role="tablist" aria-label="Setup sections" onKeyDown={onKey} className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
        {tabs.map((t) => (
          <button
            key={t.id}
            id={`tab-${t.id}`}
            role="tab"
            type="button"
            aria-selected={t.id === tab}
            aria-controls="setup-panel"
            tabIndex={t.id === tab ? 0 : -1}
            onClick={() => go(t.id)}
            className={`-mb-px min-h-11 shrink-0 border-b-2 px-4 text-[14px] transition-colors ${t.id === tab ? "border-brand font-semibold text-ink" : "border-transparent text-ink-3 hover:text-ink"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div id="setup-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="max-w-[1200px]">
        {tab === "structure" && <StructureTab canEdit={canEdit} />}
        {tab === "machines" && <MachinesTab canEdit={canEdit} />}
        {tab === "lists" && <ListsTab canEdit={canEdit} />}
        {tab === "workers" && <WorkersTab canEdit={canEdit} />}
        {tab === "users" && me && <UsersTab meId={me.id} />}
        {tab === "import" && <ImportTab />}
      </div>
    </>
  );
}

export default function SetupPage() {
  return (
    <Suspense fallback={<Loading />}>
      <SetupHub />
    </Suspense>
  );
}
