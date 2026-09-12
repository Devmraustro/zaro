import Link from "next/link";
import BrandMark from "@/components/BrandMark";

const COLUMNS = [
  {
    heading: "Collection",
    links: [
      { href: "/shop", label: "Shop" },
      { href: "/shop?sort=newest", label: "New arrivals" },
    ],
  },
  {
    heading: "Bespoke",
    links: [{ href: "/custom", label: "Custom Order" }],
  },
  {
    heading: "Studio",
    links: [{ href: "/admin", label: "Staff access" }],
  },
];

export default function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="grain overflow-hidden bg-zaro-graphite text-zaro-ivory/70">
      <div className="mx-auto max-w-[100rem] px-6 py-16 sm:px-10 lg:px-16 lg:py-20">
        <div className="grid grid-cols-1 gap-12 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <BrandMark tone="light" href="/" />
            <p className="mt-5 max-w-xs text-sm leading-relaxed text-zaro-ivory/55">
              Modern furniture and handcrafted metalwork. Built with precision,
              designed with intention.
            </p>
          </div>
          {COLUMNS.map((col) => (
            <nav key={col.heading} aria-label={col.heading}>
              <h2 className="text-[0.65rem] font-medium tracking-[0.24em] uppercase text-zaro-ivory/40">
                {col.heading}
              </h2>
              <ul className="mt-5 space-y-3">
                {col.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-zaro-ivory/80 transition-colors hover:text-zaro-bronze-light"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-14 flex flex-col gap-3 border-t border-zaro-ivory/10 pt-8 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-zaro-ivory/40">
            © {year} ZARO Studio — Modern Furniture & Metalwork
          </p>
          <p className="text-xs uppercase tracking-[0.18em] text-zaro-bronze-light/70">
            Made, not merely listed
          </p>
        </div>
      </div>
    </footer>
  );
}