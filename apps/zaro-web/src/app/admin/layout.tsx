import type { Metadata } from "next";
import Link from "next/link";
import AdminNav from "@/components/admin/AdminNav";

export const metadata: Metadata = {
  title: "Staff",
  robots: { index: false, follow: false },
};

export default function AdminLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="flex min-h-screen flex-col bg-zaro-paper md:flex-row">
      <aside className="grain shrink-0 border-b border-zaro-ivory/10 bg-zaro-graphite px-6 py-6 md:flex md:w-64 md:flex-col md:border-b-0 md:border-r">
        <div className="flex items-baseline gap-2">
          <span className="font-serif text-xl font-medium tracking-[0.18em] text-zaro-ivory">ZARO</span>
          <span className="text-[0.55rem] uppercase tracking-[0.28em] text-zaro-ivory/40">Ops</span>
        </div>
        <AdminNav />
        <div className="mt-8 hidden pt-6 md:block">
          <Link
            href="/"
            className="text-[0.65rem] uppercase tracking-[0.2em] text-zaro-ivory/40 transition-colors hover:text-zaro-ivory"
          >
            ← Public site
          </Link>
        </div>
      </aside>
      <main className="flex-1 px-6 py-8 sm:px-10">{children}</main>
    </div>
  );
}