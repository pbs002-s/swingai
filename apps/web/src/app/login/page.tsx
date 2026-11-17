"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Logo } from "@/components/Icon";
import { ApiFailure, post } from "@/lib/api";

const DEMO = process.env.NEXT_PUBLIC_DEMO === "1";
const DEMO_USERS = [
  ["admin@stitchsense.local", "Factory admin"],
  ["supervisor@stitchsense.local", "Supervisor"],
  ["quality@stitchsense.local", "Quality + maintenance"],
] as const;

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await post("/auth/login", { email: email.trim(), password });
      router.replace("/app");
    } catch (err) {
      setError(err instanceof ApiFailure ? err.message : "Could not log in. Try again.");
      setBusy(false);
    }
  }

  return (
    <main className="relative grid min-h-dvh place-items-center px-4 py-12">
      <div aria-hidden="true" className="weave pointer-events-none absolute inset-0 opacity-60" />
      <div className="relative w-full max-w-[400px]">
        <Link href="/" className="mb-8 flex items-center justify-center gap-2.5 text-ink">
          <Logo size={30} />
          <span className="text-[19px] font-semibold tracking-[-0.02em]">StitchSense</span>
        </Link>
        <div className="panel p-7 shadow-[0_24px_60px_-32px_rgb(20_22_25/0.4)]">
          <h1 className="text-[22px] font-semibold tracking-[-0.02em]">Log in</h1>
          <p className="mt-1 text-[14px] text-ink-3">Staff accounts only. Ask your factory admin for access.</p>
          <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
            <label className="flex flex-col gap-1.5 text-[14px] font-medium">
              Email
              <input className="field" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1.5 text-[14px] font-medium">
              Password
              <input className="field" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            {error && <p role="alert" className="rounded-lg bg-down-bg px-3 py-2 text-[14px] text-down">{error}</p>}
            <button type="submit" className="btn btn-primary mt-1 w-full" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
          </form>
        </div>
        {DEMO && (
          <div className="mt-5 rounded-xl border border-dashed border-line-2 p-4 text-[13px]">
            <p className="font-medium text-ink">Demo accounts · password <span className="font-mono">stitchsense-demo</span></p>
            <div className="mt-2 flex flex-col gap-1">
              {DEMO_USERS.map(([mail, role]) => (
                <button
                  key={mail}
                  type="button"
                  className="flex min-h-9 items-center justify-between rounded-md px-2 text-left text-ink-2 transition-colors hover:bg-surface hover:text-ink"
                  onClick={() => { setEmail(mail); setPassword("stitchsense-demo"); }}
                >
                  <span className="font-mono">{mail}</span>
                  <span className="text-ink-3">{role}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
