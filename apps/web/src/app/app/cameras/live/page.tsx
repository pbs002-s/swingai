"use client";

import Link from "next/link";
import { useState } from "react";
import { useApi } from "@/lib/hooks";
import { Empty, ErrorBox, Loading, PageHeader } from "@/components/app/ui";
import { Tile, Viewer } from "@/components/cameras/LiveWall";
import type { LiveCamera } from "@/components/cameras/LiveWall";

export default function LiveWallPage() {
  const cams = useApi<LiveCamera[]>("/cameras/live", 30_000);
  const [open, setOpen] = useState<number | null>(null);
  const list = cams.data ?? [];

  return (
    <>
      <PageHeader
        title="Live cameras"
        sub="Live view runs on the factory network only. Click a camera for full screen; arrow keys switch cameras."
        actions={
          <>
            <Link href="/app/cameras" className="btn">Manage cameras</Link>
            {list.length > 0 && <button className="btn btn-brand" onClick={() => setOpen(0)}>Full screen</button>}
          </>
        }
      />
      {cams.error && <ErrorBox message={cams.error.message} onRetry={cams.refresh} />}
      {cams.loading && !cams.data ? (
        <Loading />
      ) : !list.length ? (
        !cams.error && <Empty title="No cameras yet" text="Add a camera to watch it live here." />
      ) : (
        <ul className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-3">
          {list.map((c, n) => (
            <li key={c.id}><Tile cam={c} onOpen={() => setOpen(n)} /></li>
          ))}
        </ul>
      )}
      {open !== null && list.length > 0 && <Viewer cams={list} start={open} onClose={() => setOpen(null)} />}
    </>
  );
}
