"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import BrandMark from "@/components/BrandMark";
import { buttonClass } from "@/components/ui/Button";
import { Close, Menu } from "@/components/ui/icons";

const NAV = [
  { href: "/shop", label: "Shop" },
  { href: "/custom", label: "Custom Order" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function SiteHeader() {
  const pathname = usePathname();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 32);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const home = pathname === "/";
  const solid = !home || scrolled || open;
  const onDark = home && !solid;

  const linkTone = onDark ? "text-zaro-ivory/85 hover:text-zaro-ivory" : "text-zaro-graphite/80 hover:text-zaro-black";
  const underline = onDark ? "bg-zaro-ivory" : "bg-zaro-bronze";
  const hairline = solid ? "border-b border-zaro-graphite/10 bg-zaro-paper/90 backdrop-blur-md" : "border-b border-transparent bg-transparent";

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-[background-color,border-color,box-shadow] duration-300 ${hairline} ${solid && !home ? "shadow-[0_1px_0_rgba(11,11,11,0.06)]" : ""}`}
    >
      <div className="mx-auto flex h-16 max-w-[100rem] items-center justify-between px-6 sm:h-20 sm:px-10 lg:px-16">
        <BrandMark tone={onDark ? "light" : "ink"} href="/" />

        <nav aria-label="Primary" className="hidden items-center gap-10 md:flex">
          {NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`relative pb-1 text-[0.7rem] font-medium tracking-[0.2em] uppercase transition-colors duration-200 ${linkTone}`}
              >
                {item.label}
                <span
                  className={`absolute inset-x-0 -bottom-px h-px origin-left scale-x-0 transition-transform duration-300 ease-out ${underline} ${active ? "scale-x-100" : ""}`}
                  aria-hidden="true"
                />
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          <Link
            href="/admin"
            className={`hidden text-[0.65rem] font-medium tracking-[0.2em] uppercase transition-colors sm:block ${
              onDark ? "text-zaro-ivory/50 hover:text-zaro-ivory" : "text-zaro-stone hover:text-zaro-graphite"
            }`}
          >
            Admin
          </Link>
          <Link
            href="/custom"
            className={buttonClass(
              "primary",
              `hidden px-5 py-2.5 md:inline-flex ${onDark ? "bg-zaro-ivory text-zaro-black hover:bg-zaro-paper" : ""}`,
            )}
          >
            Start a project
          </Link>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="site-nav"
            aria-label={open ? "Close menu" : "Open menu"}
            className={`inline-flex size-10 items-center justify-center transition-colors md:hidden ${
              onDark ? "text-zaro-ivory" : "text-zaro-graphite"
            }`}
          >
            {open ? <Close className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      {/* Mobile panel */}
      <div
        id="site-nav"
        className={`overflow-hidden border-t border-zaro-graphite/10 bg-zaro-paper/95 backdrop-blur-md transition-[max-height,opacity] duration-300 md:hidden ${
          open ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <nav aria-label="Mobile" className="flex flex-col px-6 py-6">
          {NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className="border-b border-zaro-graphite/8 py-4 font-serif text-2xl text-zaro-black transition-colors hover:text-zaro-bronze"
              >
                {item.label}
              </Link>
            );
          })}
          <Link
            href="/custom"
            className={`mt-5 ${buttonClass("primary", "w-full")}`}
          >
            Start a project
          </Link>
          <Link href="/admin" className="mt-4 text-center text-[0.65rem] uppercase tracking-[0.2em] text-zaro-stone hover:text-zaro-graphite">
            Admin
          </Link>
        </nav>
      </div>
    </header>
  );
}