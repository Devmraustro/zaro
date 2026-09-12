"use client";

import { usePathname } from "next/navigation";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";

/**
 * Public chrome is hidden inside the /admin area, which has its own shell.
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAdmin = pathname.startsWith("/admin");
  return (
    <>
      <a
        href="#site-main"
        className="sr-only z-[100] bg-zaro-black px-4 py-2 text-sm text-zaro-ivory focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      {!isAdmin && <SiteHeader />}
      <div id="site-main">{children}</div>
      {!isAdmin && <SiteFooter />}
    </>
  );
}