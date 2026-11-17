import type { Metadata } from "next";
import { Shell } from "@/components/app/Shell";

export const metadata: Metadata = { title: "Dashboard", robots: { index: false } };

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <Shell>{children}</Shell>;
}
