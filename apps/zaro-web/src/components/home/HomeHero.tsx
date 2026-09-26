import Link from "next/link";
import BrandPhoto from "@/components/BrandPhoto";
import Reveal from "@/components/ui/Reveal";
import { buttonClass } from "@/components/ui/Button";
import { ArrowRight } from "@/components/ui/icons";

/** Restrained "what the studio makes" line — technical, not marketing. */
const MAKES = ["Tables", "Consoles", "Shelving", "Railings", "Bespoke"];

export default function HomeHero() {
  return (
    <section className="relative min-h-[100svh] w-full overflow-hidden bg-zaro-ink">
      {/* Drafting backdrop. Real photography (public/images/hero-interior.*)
          drops in automatically and renders above the same scrim stack. */}
      <div aria-hidden="true" className="absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 scale-105 opacity-45">
          <BrandPhoto name="hero-interior" priority />
        </div>
        {/* Vignette first, then a bottom-weighted scrim: keeps the technical
            drawing readable but always subordinate to the headline. */}
        <div className="absolute inset-0 bg-[radial-gradient(120%_95%_at_50%_8%,rgba(19,19,17,0)_0%,rgba(19,19,17,0.35)_62%,rgba(19,19,17,0.9)_100%)]" />
        <div className="absolute inset-0 bg-gradient-to-t from-zaro-ink via-zaro-ink/60 to-zaro-ink/25" />
        <div className="grain absolute inset-0 opacity-60" />
      </div>

      <div className="relative mx-auto flex min-h-[100svh] max-w-[100rem] flex-col justify-end px-6 pt-40 pb-16 sm:px-10 sm:pb-20 lg:px-16 lg:pt-44 lg:pb-24">
        <Reveal>
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.32em] text-zaro-bronze-light sm:text-[0.7rem]">
            ZARO — Handcrafted · Premium · Bespoke
          </p>
        </Reveal>

        <Reveal delay={1}>
          <h1 className="mt-6 max-w-4xl font-serif text-[clamp(2.35rem,7.2vw,4.5rem)] font-medium leading-[1.04] tracking-[-0.015em] text-zaro-ivory text-balance sm:mt-7 sm:text-6xl lg:text-7xl xl:text-[4.75rem]">
            Furniture and metalwork,
            <br className="hidden sm:block" />
            engineered by hand.
          </h1>
        </Reveal>

        <Reveal delay={2}>
          <p className="mt-6 max-w-xl text-[0.98rem] leading-relaxed text-zaro-ivory/75 sm:mt-7 sm:text-[1.02rem]">
            A studio for bespoke tables, consoles, shelving and architectural
            metalwork — designed to your space, fabricated to your
            specification, finished by hand.
          </p>
        </Reveal>

        <Reveal delay={3}>
          <div className="mt-9 flex flex-col items-stretch gap-3 sm:mt-10 sm:flex-row sm:flex-wrap sm:items-center sm:gap-4">
            <Link
              href="/shop"
              className={buttonClass("light", "px-7 py-3.5 sm:px-8 sm:py-4")}
            >
              SHOP COLLECTION
              <ArrowRight className="size-4 transition-transform duration-300 group-hover/btn:translate-x-0.5" />
            </Link>
            <Link
              href="/custom"
              className={buttonClass(
                "outline",
                "border-zaro-ivory/40 px-7 py-3.5 text-zaro-ivory hover:border-zaro-ivory hover:bg-zaro-ivory hover:text-zaro-ink sm:px-8 sm:py-4",
              )}
            >
              CUSTOM ORDER
            </Link>
          </div>
        </Reveal>

        <Reveal delay={3}>
          <ul className="mt-10 hidden items-center gap-x-6 gap-y-2 border-t border-zaro-ivory/10 pt-5 sm:mt-12 sm:flex sm:flex-wrap">
            {MAKES.map((item) => (
              <li
                key={item}
                className="font-mono text-[0.625rem] uppercase tracking-[0.24em] text-zaro-ivory/40"
              >
                {item}
              </li>
            ))}
          </ul>
        </Reveal>
      </div>

      <div
        aria-hidden="true"
        className="absolute bottom-0 left-12 hidden h-20 w-px origin-bottom animate-[scroll-line_2.8s_var(--ease-out-quart)_infinite] bg-gradient-to-t from-zaro-bronze-light to-transparent sm:block lg:left-16"
      />
    </section>
  );
}
