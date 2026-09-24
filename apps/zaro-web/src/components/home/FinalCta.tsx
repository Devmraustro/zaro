import Link from "next/link";
import BrandPhoto from "@/components/BrandPhoto";
import Reveal from "@/components/ui/Reveal";
import { buttonClass } from "@/components/ui/Button";
import { ArrowRight } from "@/components/ui/icons";

export default function FinalCta() {
  return (
    <section id="contact" className="relative overflow-hidden bg-zaro-ink">
      <div className="absolute inset-0 opacity-30">
        <BrandPhoto name="hero-interior" />
        <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-zaro-ink via-zaro-ink/70 to-zaro-ink/40" />
      </div>
      <div aria-hidden="true" className="grain absolute inset-0" />

      <div className="relative mx-auto flex max-w-[100rem] flex-col items-center px-6 py-28 text-center sm:px-10 sm:py-36 lg:px-16">
        <Reveal>
          <p className="eyebrow justify-center text-zaro-bronze-light">Start a project</p>
        </Reveal>
        <Reveal delay={1}>
          <h2 className="mt-6 max-w-4xl font-serif text-4xl font-medium leading-[1.02] tracking-[-0.015em] text-zaro-ivory text-balance sm:text-6xl lg:text-7xl">
            Let&apos;s build something distinctive.
          </h2>
        </Reveal>
        <Reveal delay={2}>
          <p className="mt-6 max-w-xl text-[1.02rem] leading-relaxed text-zaro-ivory/70">
            Share your space and your measurements. We design the piece, confirm every
            detail, then build it in our studio.
          </p>
        </Reveal>
        <Reveal delay={3}>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link href="/custom" className={buttonClass("light")}>
              Request a custom project
              <ArrowRight className="size-4 transition-transform duration-300 group-hover/btn:translate-x-0.5" />
            </Link>
            <Link
              href="/shop"
              className={buttonClass(
                "outline",
                "border-zaro-ivory/35 text-zaro-ivory hover:border-zaro-ivory hover:bg-zaro-ivory hover:text-zaro-ink",
              )}
            >
              Explore products
            </Link>
          </div>
        </Reveal>
      </div>
    </section>
  );
}