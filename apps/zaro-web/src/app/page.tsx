import Link from "next/link";
import BrandPhoto from "@/components/BrandPhoto";
import Reveal from "@/components/ui/Reveal";
import { Section, SectionHeading } from "@/components/ui/Section";
import { buttonClass } from "@/components/ui/Button";
import { ArrowRight } from "@/components/ui/icons";

const DISCIPLINES = [
  {
    key: "chair-dining" as const,
    eyebrow: "01 — Seating",
    title: "Dining Chairs",
    copy: "Sculptural seats that hold a room — joined, shaped and finished by hand.",
    href: "/shop",
  },
  {
    key: "table-dining" as const,
    eyebrow: "02 — Tables",
    title: "Dining & Occasional Tables",
    copy: "Considered tops on precise frames, in solid timber and blackened steel.",
    href: "/shop",
  },
  {
    key: "metalwork" as const,
    eyebrow: "03 — Metalwork",
    title: "Custom Metalwork",
    copy: "Frames, brackets and architectural steelwork — welded, ground and refined.",
    href: "/custom",
  },
  {
    key: "custom-furniture" as const,
    eyebrow: "04 — Bespoke",
    title: "Custom Furniture",
    copy: "When the standard piece isn't enough, we build to your exact specification.",
    href: "/custom",
  },
];

const PRINCIPLES = [
  {
    title: "Designed like architecture",
    copy: "Proportion, line and load are considered before material is ever cut.",
  },
  {
    title: "Built by hand",
    copy: "Joining, welding and finishing happen in our studio — not on a line.",
  },
  {
    title: "Made to your spec",
    copy: "Dimensions, materials and finish can be tailored to the piece you need.",
  },
];

export default function HomePage() {
  return (
    <main>
      {/* ------------------------------------------------ Hero */}
      <section className="relative min-h-[94svh] w-full overflow-hidden bg-zaro-graphite">
        <div className="absolute inset-0">
          <BrandPhoto name="hero-interior" priority />
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-gradient-to-t from-zaro-black/85 via-zaro-black/25 to-zaro-black/10"
          />
          <div aria-hidden="true" className="grain absolute inset-0" />
        </div>

        <div className="relative mx-auto flex min-h-[94svh] max-w-[100rem] flex-col justify-end px-6 pb-24 pt-32 sm:px-10 lg:px-16">
          <Reveal>
            <p className="eyebrow text-zaro-bronze-light">Modern furniture & metalwork</p>
          </Reveal>
          <Reveal delay={1}>
            <h1 className="mt-6 max-w-4xl font-serif text-[2.75rem] font-medium leading-[1.04] tracking-[-0.015em] text-zaro-ivory text-balance sm:text-6xl lg:text-7xl">
              Furniture and metalwork,
              <br className="hidden sm:block" /> engineered by hand.
            </h1>
          </Reveal>
          <Reveal delay={2}>
            <p className="mt-6 max-w-xl text-[1.02rem] leading-relaxed text-zaro-ivory/75">
              Precision-built pieces for considered modern interiors — designed with intention,
              made to last, and made to your specification when the standard isn&apos;t enough.
            </p>
          </Reveal>
          <Reveal delay={3}>
            <div className="mt-10 flex flex-wrap items-center gap-4">
              <Link href="/shop" className={buttonClass("light")}>
                Shop collection
                <ArrowRight className="size-4 transition-transform duration-300 group-hover/btn:translate-x-0.5" />
              </Link>
              <Link
                href="/custom"
                className={buttonClass(
                  "outline",
                  "border-zaro-ivory/35 text-zaro-ivory hover:border-zaro-ivory hover:bg-zaro-ivory hover:text-zaro-graphite",
                )}
              >
                Custom order
              </Link>
            </div>
          </Reveal>
        </div>

        <div
          aria-hidden="true"
          className="absolute bottom-0 left-12 hidden h-16 w-px origin-bottom animate-[scroll-line_2.6s_var(--ease-out-quart)_infinite] bg-gradient-to-t from-zaro-bronze-light to-transparent sm:block lg:left-16"
        />
      </section>

      {/* ------------------------------------------------ Statement */}
      <Section className="py-24 sm:py-32">
        <div className="grid grid-cols-1 items-start gap-10 lg:grid-cols-[1.1fr_0.9fr]">
          <Reveal>
            <SectionHeading
              eyebrow="The studio"
              title="Precision is the foundation. Craft is the finish."
            />
          </Reveal>
          <Reveal delay={1}>
            <div className="space-y-5 text-[0.98rem] leading-relaxed text-zaro-graphite/80">
              <p>
                ZARO designs and builds modern furniture and custom metalwork as a single
                practice — architecture informs every piece, and every piece is finished by hand.
              </p>
              <p>
                The result is a quiet, premium collection: nothing decorative for its own sake,
                everything resolved in line, material and joinery.
              </p>
              <Link
                href="/shop"
                className="inline-flex items-center gap-2 pt-1 text-[0.72rem] font-medium uppercase tracking-[0.2em] text-zaro-bronze-dark transition-colors hover:text-zaro-graphite"
              >
                Explore the collection
                <ArrowRight className="size-4" />
              </Link>
            </div>
          </Reveal>
        </div>
      </Section>

      {/* ------------------------------------------------ Disciplines */}
      <Section className="pb-24 sm:pb-32">
        <Reveal>
          <SectionHeading
            eyebrow="What we craft"
            title="Four disciplines, one studio"
            align="center"
          />
        </Reveal>
        <div className="mt-14 grid grid-cols-1 gap-x-6 gap-y-14 sm:grid-cols-2 lg:grid-cols-4">
          {DISCIPLINES.map((d, i) => (
            <Reveal key={d.key} delay={i % 2 === 0 ? 0 : 1}>
              <Link href={d.href} className="group block">
                <div className="relative aspect-[4/5] w-full overflow-hidden">
                  <BrandPhoto name={d.key} className="" />
                  <div
                    aria-hidden="true"
                    className="absolute inset-0 bg-zaro-black/0 transition-colors duration-300 group-hover:bg-zaro-black/[0.05]"
                  />
                </div>
                <p className="mt-4 font-mono text-[0.625rem] uppercase tracking-[0.18em] text-zaro-stone">
                  {d.eyebrow}
                </p>
                <h3 className="mt-1.5 font-serif text-xl font-medium text-zaro-black transition-colors duration-200 group-hover:text-zaro-bronze">
                  {d.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-zaro-steel">{d.copy}</p>
              </Link>
            </Reveal>
          ))}
        </div>
      </Section>

      {/* ------------------------------------------------ Craftsmanship */}
      <section className="grain overflow-hidden bg-zaro-graphite">
        <div className="grid grid-cols-1 lg:grid-cols-2">
          <div className="relative min-h-[24rem] lg:min-h-full">
            <BrandPhoto name="craftsmanship" className="" />
          </div>
          <div className="flex flex-col justify-center px-6 py-20 sm:px-10 lg:px-16 lg:py-28">
            <Reveal>
              <p className="eyebrow text-zaro-bronze-light">Craft & materials</p>
              <h2 className="mt-5 font-serif text-3xl font-medium leading-[1.08] text-zaro-ivory sm:text-4xl">
                Made, not merely listed.
              </h2>
              <p className="mt-5 max-w-lg text-[0.98rem] leading-relaxed text-zaro-ivory/70">
                Every ZARO piece moves through the same hands — cut, welded, ground and finished
                in our studio. That is the difference between furniture and objects that are
                simply sold.
              </p>
            </Reveal>
            <div className="mt-12 grid grid-cols-1 gap-8 sm:grid-cols-3">
              {PRINCIPLES.map((p, i) => (
                <Reveal key={p.title} delay={i % 3 === 0 ? 0 : i % 3 === 1 ? 1 : 2}>
                  <div className="border-t border-zaro-ivory/15 pt-5">
                    <h3 className="font-serif text-lg font-medium text-zaro-ivory">{p.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-zaro-ivory/55">{p.copy}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ Bespoke CTA */}
      <Section className="py-24 sm:py-32">
        <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="order-2 lg:order-1">
            <Reveal>
              <p className="eyebrow text-zaro-bronze-dark">Bespoke service</p>
              <h2 className="mt-5 font-serif text-3xl font-medium leading-[1.08] text-zaro-black sm:text-4xl">
                Have something specific in mind?
              </h2>
              <p className="mt-5 max-w-lg text-[0.98rem] leading-relaxed text-zaro-graphite/80">
                Tell us about your space, your measurements and your materials. We refine the
                design, confirm every detail, then build the piece in our studio.
              </p>
              <div className="mt-8 flex flex-wrap gap-4">
                <Link href="/custom" className={buttonClass("primary")}>
                  Start a custom order
                  <ArrowRight className="size-4 transition-transform duration-300 group-hover/btn:translate-x-0.5" />
                </Link>
              </div>
            </Reveal>
          </div>
          <Reveal delay={1} className="order-1 lg:order-2">
            <div className="relative aspect-[4/3] w-full overflow-hidden">
              <BrandPhoto name="custom-furniture" className="" />
            </div>
          </Reveal>
        </div>
      </Section>
    </main>
  );
}