"use client";

import Link from "next/link";
import { Fragment, useState } from "react";
import { ApiFailure, api, patch } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { hasRole, useMe } from "@/components/app/Shell";
import { Empty, ErrorBox, Loading, PageHeader, minutesSince } from "@/components/app/ui";
import { CameraZonesPanel } from "@/components/cameras/CameraZonesPanel";
import type { Camera } from "@/lib/types-cameras";

function Status({ camera }: { camera: Camera }) {
  if (!camera.is_active) return <span className="text-[13px] text-ink-3">Disabled</span>;
  const seen = camera.last_seen_at ? `, last seen ${minutesSince(camera.last_seen_at)} ago` : "";
  return (
    <span className={`flex items-center gap-1.5 text-[13px] ${camera.online ? "text-run" : "text-ink-2"}`}>
      <span className={`size-2 rounded-full ${camera.online ? "bg-run" : "border border-off"}`} aria-hidden="true" />
      {camera.online ? "Online" : `Offline${seen}`}
    </span>
  );
}

export default function CamerasPage() {
  const me = useMe();
  const canEdit = hasRole(me, "factory_admin");
  const cams = useApi<Camera[]>("/cameras", 15_000);
  const [editing, setEditing] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function setActive(c: Camera, active: boolean) {
    if (!active && !window.confirm(`Disable ${c.name}? It stops sending events; its history is kept.`)) return;
    setError(null);
    try {
      await (active ? patch(`/cameras/${c.id}`, { is_active: true }) : api(`/cameras/${c.id}`, { method: "DELETE" }));
      void cams.refresh();
    } catch (e) {
      setError(e instanceof ApiFailure ? e.message : "Could not change the camera.");
    }
  }

  return (
    <>
      <PageHeader
        title="Cameras"
        sub="Cameras connect through an edge box on the floor. Raw video never leaves the factory."
        actions={canEdit && <Link href="/app/cameras/new" className="btn btn-brand">Add camera</Link>}
      />
      {error && <div className="mb-4"><ErrorBox message={error} /></div>}
      <section aria-labelledby="cams-h" className="panel overflow-hidden">
        <h2 id="cams-h" className="sr-only">Camera list</h2>
        {cams.error && <div className="p-4"><ErrorBox message={cams.error.message} onRetry={cams.refresh} /></div>}
        {cams.loading && !cams.data ? (
          <div className="p-4"><Loading /></div>
        ) : !cams.data?.length ? (
          !cams.error && <Empty title="No cameras yet" text={canEdit ? "Add a camera to start watching stations." : "A factory admin adds cameras."} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[14px]">
              <thead className="border-b border-line text-[12px] text-ink-3">
                <tr>
                  <th scope="col" className="px-5 py-3 font-medium">Camera</th>
                  <th scope="col" className="px-3 py-3 font-medium">Status</th>
                  <th scope="col" className="px-3 py-3 font-medium">Stations</th>
                  <th scope="col" className="px-3 py-3 font-medium">Purpose</th>
                  <th scope="col" className="px-3 py-3 font-medium">Zones</th>
                  {canEdit && <th scope="col" className="px-5 py-3 font-medium"><span className="sr-only">Actions</span></th>}
                </tr>
              </thead>
              <tbody>
                {cams.data.map((c) => (
                  <Fragment key={c.id}>
                    <tr className="border-b border-line last:border-b-0">
                      <td className="px-5 py-3">
                        <span className="flex flex-col">
                          <span className="font-medium">{c.name}</span>
                          <span className="font-mono text-[12px] text-ink-3">{c.code}{c.connection ? ` · ${c.connection.host}` : ""}</span>
                        </span>
                      </td>
                      <td className="px-3 py-3"><Status camera={c} /></td>
                      <td className="px-3 py-3 font-mono text-[13px]">{c.stations.map((s) => s.code).join(", ") || "—"}</td>
                      <td className="px-3 py-3">{c.purpose === "activity" ? "Activity" : "Seam inspection"} · {c.fps} fps</td>
                      <td className="px-3 py-3">{c.zones_count}</td>
                      {canEdit && (
                        <td className="px-5 py-3">
                          <span className="flex justify-end gap-2">
                            {c.is_active && (
                              <button type="button" className="btn btn-ghost" aria-expanded={editing === c.id} aria-label={`Edit zones for ${c.name}`} onClick={() => setEditing(editing === c.id ? null : c.id)}>
                                Edit zones
                              </button>
                            )}
                            <button type="button" className="btn btn-ghost" aria-label={`${c.is_active ? "Disable" : "Enable"} ${c.name}`} onClick={() => setActive(c, !c.is_active)}>
                              {c.is_active ? "Disable" : "Enable"}
                            </button>
                          </span>
                        </td>
                      )}
                    </tr>
                    {editing === c.id && (
                      <tr>
                        <td colSpan={6} className="p-0">
                          <CameraZonesPanel camera={c} onSaved={cams.refresh} onClose={() => setEditing(null)} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
