"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import BrandMark from "@/components/BrandMark";
import { buttonClass } from "@/components/ui/Button";
import { ArrowUpRight, Close, Menu } from "@/components/ui/icons";

/**
 * Public navigation. Staff entry intentionally lives only in the footer
 * ("Staff access") so it never competes with the customer-facing items.
 */
const NAV = [
  { href: "/shop", label: "SHOP" },
  { href: "/custom", label: "CUSTOM ORDER" },
  { href: "/#work", label: "WORK" },
  { href: "/#materials", label: "MATERIALS" },
  { href: "/#about", label: "ABOUT" },
  { href: "/#contact", label: "CONTACT" },
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
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const home = pathname === "/";
  const solid = !home || scrolled || open;
  // Over the dark hero the chrome stays dark; on the light interior pages it
  // settles to the warm ivory bar. Both are translucent and blurred.
  const onDark = home && !solid;
  const compact = scrolled || open;

  const linkTone = onDark
    ? "text-zaro-ivory/80 hover:text-zaro-ivory"
    : "text-zaro-graphite/75 hover:text-zaro-black";
  const underline = onDark ? "bg-zaro-ivory" : "bg-zaro-bronze";
  const navTone = onDark ? "text-zaro-ivory" : "text-zaro-graphite";
  const shell = onDark
    ? "border-b border-transparent bg-transparent"
    : home
      ? "border-b border-zaro-ivory/10 bg-zaro-ink/80 shadow-[0_1px_0_rgba(242,238,230,0.06)] backdrop-blur-xl"
      : "border-b border-zaro-graphite/10 bg-zaro-ivory/85 shadow-[0_1px_0_rgba(11,11,11,0.06)] backdrop-blur-xl";

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-[background-color,border-color,box-shadow,backdrop-filter] duration-500 ease-out ${shell}`}
    >
      {/* Legibility scrim only while the bar is transparent over the hero. */}
      {onDark ? (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-zaro-ink/70 to-transparent"
        />
      ) : null}

      <div
        className={`relative mx-auto flex max-w-[100rem] items-center justify-between px-6 transition-[height] duration-500 ease-out sm:px-10 lg:px-16 ${
          compact ? "h-16 lg:h-[4.5rem]" : "h-20 sm:h-24"
        }`}
      >
        <BrandMark tone={onDark ? "light" : "ink"} href="/" />

        <nav aria-label="Primary" className="hidden items-center gap-5 lg:flex xl:gap-8">
          {NAV.map((item) => {
            const isRoute = ROUTES.some((r) => r === item.href.split("#")[0]);
            const active = isRoute && isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`relative py-1 text-[0.68rem] font-medium tracking-[0.18em] uppercase transition-colors duration-200 xl:text-[0.7rem] xl:tracking-[0.2em] ${linkTone}`}
              >
                {item.label}
                <span
                  className={`absolute inset-x-0 bottom-0 h-px origin-left scale-x-0 transition-transform duration-300 ease-out ${underline} ${active ? "scale-x-100" : ""}`}
                  aria-hidden="true"
                />
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          <Link
            href="/custom"
            className={buttonClass(
              "primary",
              `hidden px-6 py-3 lg:inline-flex xl:px-7 ${onDark ? "bg-zaro-ivory text-zaro-black hover:bg-zaro-paper" : ""}`,
            )}
          >
            START A PROJECT
          </Link>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="site-nav"
            aria-label={open ? "Close menu" : "Open menu"}
            className={`-mr-2 inline-flex size-11 items-center justify-center transition-colors lg:hidden ${navTone}`}
          >
            {open ? <Close className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      {/* Mobile panel */}
      <div
        id="site-nav"
        inert={!open}
        className={`overflow-hidden transition-[max-height,opacity] duration-300 ease-out lg:hidden ${
          onDark ? "bg-zaro-ink/95 backdrop-blur-xl" : "bg-zaro-ivory/95 backdrop-blur-xl"
        } ${open ? "max-h-[32rem] opacity-100" : "max-h-0 opacity-0"}`}
      >
        <nav aria-label="Mobile" className="flex flex-col px-6 pt-2 pb-7 sm:px-10">
          {NAV.map((item) => {
            const isRoute = ROUTES.some((r) => r === item.href.split("#")[0]);
            const active = isRoute && isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center justify-between border-b py-4 text-[0.8rem] font-medium uppercase tracking-[0.2em] transition-colors ${
                  onDark ? "border-zaro-ivory/10 text-zaro-ivory/80" : "border-zaro-graphite/10 text-zaro-black"
                }`}
              >
                {item.label}
                <ArrowUpRight className="size-4 shrink-0 text-zaro-bronze" />
              </Link>
            );
          })}
          <Link
            href="/custom"
            className={buttonClass(
              "primary",
              `mt-7 w-full py-4 ${onDark ? "bg-zaro-ivory text-zaro-black hover:bg-zaro-paper" : ""}`,
            )}
          >
            START A PROJECT
          </Link>
        </nav>
      </div>
    </header>
  );
}
