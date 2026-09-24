import Link from "next/link";
import BrandMark from "@/components/BrandMark";

const NAVIGATION = [
  { href: "/#work", label: "Work" },
  { href: "/shop", label: "Products" },
  { href: "/custom", label: "Custom Design" },
  { href: "/#materials", label: "Materials" },
  { href: "/#about", label: "About" },
  { href: "/#contact", label: "Contact" },
];

const STUDIO = [
  { href: "/track", label: "Track an order" },
  { href: "/custom", label: "Request a quote" },
  { href: "/shop", label: "The collection" },
];

export default function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="grain overflow-hidden bg-zaro-ink text-zaro-ivory/70">
      <div className="mx-auto max-w-[100rem] px-6 py-16 sm:px-10 lg:px-16 lg:py-20">
        <div className="grid grid-cols-1 gap-12 md:grid-cols-[1.3fr_1fr_1fr]">
          <div>
            <BrandMark tone="light" href="/" />
            <p className="mt-5 max-w-xs text-sm leading-relaxed text-zaro-ivory/55">
              Handcrafted furniture and architectural metalwork. Drawn like
              architecture, built by hand, finished to spec.
            </p>
          </div>

          <nav aria-label="Navigation">
            <h2 className="text-[0.65rem] font-medium tracking-[0.24em] uppercase text-zaro-ivory/40">
              Navigation
            </h2>
            <ul className="mt-5 space-y-3">
              {NAVIGATION.map((link) => (
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

          <nav aria-label="Studio">
            <h2 className="text-[0.65rem] font-medium tracking-[0.24em] uppercase text-zaro-ivory/40">
              Studio
            </h2>
            <ul className="mt-5 space-y-3">
              {STUDIO.map((link) => (
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
        </div>

        <div className="mt-14 flex flex-col gap-3 border-t border-zaro-ivory/10 pt-8 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-zaro-ivory/40">
            © {year} ZARO Studio — Modern Furniture & Metalwork
          </p>
          <Link
            href="/admin"
            className="text-[0.625rem] uppercase tracking-[0.18em] text-zaro-ivory/30 transition-colors hover:text-zaro-ivory/60"
          >
            Staff access
          </Link>
        </div>
      </div>
    </footer>
  );
}