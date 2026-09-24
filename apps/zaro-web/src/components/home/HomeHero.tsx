import Link from "next/link";
import BrandPhoto from "@/components/BrandPhoto";
import Reveal from "@/components/ui/Reveal";
import { buttonClass } from "@/components/ui/Button";
import { ArrowRight } from "@/components/ui/icons";

export default function HomeHero() {
  return (
    <section className="relative min-h-[100svh] w-full overflow-hidden bg-zaro-ink">
      <div className="absolute inset-0">
        <BrandPhoto name="hero-interior" priority />
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-t from-zaro-ink via-zaro-ink/30 to-zaro-ink/20"
        />
        <div aria-hidden="true" className="grain absolute inset-0" />
      </div>

      <div className="relative mx-auto flex min-h-[100svh] max-w-[100rem] flex-col justify-end px-6 pb-20 pt-36 sm:px-10 lg:px-16 lg:pb-24">
        <Reveal>
          <p className="font-mono text-[0.7rem] uppercase tracking-[0.3em] text-zaro-bronze-light">
            ZARO — Handcrafted · Architectural · Custom
          </p>
        </Reveal>
        <Reveal delay={1}>
          <h1 className="mt-7 max-w-5xl font-serif text-[2.9rem] font-medium leading-[1.02] tracking-[-0.015em] text-zaro-ivory text-balance sm:text-6xl lg:text-7xl xl:text-[5.25rem]">
            Furniture and architectural metalwork, engineered by hand.
          </h1>
        </Reveal>
        <Reveal delay={2}>
          <p className="mt-7 max-w-xl text-[1.02rem] leading-relaxed text-zaro-ivory/75">
            A studio for custom tables, consoles, shelving and decorative structures —
            designed to your space, built to your specification, finished by hand.
          </p>
        </Reveal>
        <Reveal delay={3}>
          <div className="mt-11 flex flex-wrap items-center gap-4">
            <Link href="/#work" className={buttonClass("light")}>
              Explore our work
              <ArrowRight className="size-4 transition-transform duration-300 group-hover/btn:translate-x-0.5" />
            </Link>
            <Link
              href="/custom"
              className={buttonClass(
                "outline",
                "border-zaro-ivory/35 text-zaro-ivory hover:border-zaro-ivory hover:bg-zaro-ivory hover:text-zaro-ink",
              )}
            >
              Request a custom design
            </Link>
          </div>
        </Reveal>
      </div>

      <div
        aria-hidden="true"
        className="absolute bottom-0 left-12 hidden h-20 w-px origin-bottom animate-[scroll-line_2.8s_var(--ease-out-quart)_infinite] bg-gradient-to-t from-zaro-bronze-light to-transparent sm:block lg:left-16"
      />
    </section>
  );
}