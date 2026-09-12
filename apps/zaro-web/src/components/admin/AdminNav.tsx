"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/admin", label: "Dashboard", match: (p: string) => p === "/admin" },
  { href: "/admin/products", label: "Products", match: (p: string) => p.startsWith("/admin/products") },
  {
    href: "/admin/custom-requests",
    label: "Custom Requests",
    match: (p: string) => p.startsWith("/admin/custom-requests"),
  },
];

export default function AdminNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Staff" className="mt-7 flex gap-2 overflow-x-auto md:flex-col md:gap-1">
      {LINKS.map((link) => {
        const active = link.match(pathname);
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={`whitespace-nowrap rounded-sm px-3 py-2 text-sm transition-colors ${
              active ? "bg-zaro-ivory/10 font-medium text-zaro-ivory" : "text-zaro-ivory/55 hover:text-zaro-ivory"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}