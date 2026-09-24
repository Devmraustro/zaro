"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import BrandMark from "@/components/BrandMark";
import { buttonClass } from "@/components/ui/Button";
import { ArrowUpRight, Close, Menu } from "@/components/ui/icons";

const NAV = [
  { href: "/#work", label: "Work" },
  { href: "/shop", label: "Products" },
  { href: "/custom", label: "Custom Design" },
  { href: "/#materials", label: "Materials" },
  { href: "/#about", label: "About" },
  { href: "/#contact", label: "Contact" },
];

const ROUTES = ["/shop", "/custom"];

function isActive(pathname: string, href: string): boolean {
  const path = href.split("#")[0];
  if (path === "") return false;
  return pathname === path || pathname.startsWith(`${path}/`);
}

export default function SiteHeader() {
  const pathname = usePathname();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const home = pathname === "/";
  const solid = !home || scrolled || open;
  const onDark = home && !solid;
  const compact = scrolled || open;

  const linkTone = onDark ? "text-zaro-ivory/85 hover:text-zaro-ivory" : "text-zaro-graphite/80 hover:text-zaro-black";
  const underline = onDark ? "bg-zaro-ivory" : "bg-zaro-bronze";
  const hairline = solid
    ? "border-b border-zaro-graphite/10 bg-zaro-ivory/85 shadow-[0_1px_0_rgba(11,11,11,0.06)] backdrop-blur-xl"
    : "border-b border-transparent bg-transparent";

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-[background-color,border-color,box-shadow,backdrop-filter] duration-300 ${hairline}`}
    >
      <div
        className={`mx-auto flex max-w-[100rem] items-center justify-between px-6 transition-[height] duration-300 sm:px-10 lg:px-16 ${
          compact ? "h-14" : "h-16 sm:h-20"
        }`}
      >
        <BrandMark tone={onDark ? "light" : "ink"} href="/" />

        <nav aria-label="Primary" className="hidden items-center gap-8 lg:flex">
          {NAV.map((item) => {
            const isRoute = ROUTES.some((r) => r === item.href.split("#")[0]);
            const active = isRoute && isActive(pathname, item.href);
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
            href="/custom"
            className={buttonClass(
              "primary",
              `hidden px-5 py-2.5 lg:inline-flex ${onDark ? "bg-zaro-ivory text-zaro-black hover:bg-zaro-paper" : ""}`,
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
            className={`inline-flex size-10 items-center justify-center transition-colors lg:hidden ${
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
        className={`overflow-hidden border-t border-zaro-graphite/10 bg-zaro-ivory/95 backdrop-blur-xl transition-[max-height,opacity] duration-300 lg:hidden ${
          open ? "max-h-[28rem] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <nav aria-label="Mobile" className="flex flex-col px-6 py-6">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="border-b border-zaro-graphite/8 py-4 font-serif text-2xl text-zaro-black transition-colors hover:text-zaro-bronze"
            >
              <span className="flex items-center justify-between">
                {item.label}
                <ArrowUpRight className="size-4 text-zaro-bronze" />
              </span>
            </Link>
          ))}
          <Link href="/custom" className={`mt-6 ${buttonClass("primary", "w-full")}`}>
            Start a project
          </Link>
        </nav>
      </div>
    </header>
  );
}