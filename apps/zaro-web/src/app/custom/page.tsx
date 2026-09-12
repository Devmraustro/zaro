import type { Metadata } from "next";
import BrandPhoto from "@/components/BrandPhoto";
import CustomRequestForm from "@/components/CustomRequestForm";
import Reveal from "@/components/ui/Reveal";
import { Check } from "@/components/ui/icons";

export const metadata: Metadata = {
  title: "Custom Order",
  description:
    "Commission bespoke furniture and custom metalwork — designed around your space, your dimensions and your materials. Built by hand in the ZARO studio.",
  openGraph: { title: "Custom Order · ZARO", url: "/custom" },
};

const PROCESS = [
  {
    n: "01",
    title: "Share your vision",
    copy: "Describe the piece, the space and any reference material — dimension, materials, finish, budget.",
  },
  {
    n: "02",
    title: "We refine the design",
    copy: "Your brief becomes a resolved design: proportions, joinery and finish are confirmed before we build.",
  },
  {
    n: "03",
    title: "Precision build",
    copy: "The piece is made in our studio — timber cut and joined, steel welded and ground, all finished by hand.",
  },
  {
    n: "04",
    title: "Arranged delivery",
    copy: "We agree delivery or collection for your finished piece, and confirm every detail along the way.",
  },
];

const REASSURANCE = [
  "No fixed range — adapt any piece from the collection",
  "Your dimensions, your materials, your finish",
  "A clear conversation from first sketch to delivery",
];

export default function CustomPage() {
  return (
    <main className="pb-28">
      {/* Bespoke intro */}
      <section className="mx-auto grid max-w-[100rem] grid-cols-1 gap-12 px-6 pt-32 sm:px-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-20 lg:px-16 lg:pt-40">
        <div className="flex flex-col justify-center">
          <Reveal>
            <p className="eyebrow text-zaro-bronze-dark">Bespoke service</p>
            <h1 className="mt-5 font-serif text-4xl font-medium leading-[1.05] tracking-[-0.01em] text-zaro-black sm:text-5xl lg:text-[3.4rem]">
              Furniture designed around you.
            </h1>
            <p className="mt-6 max-w-xl text-[1rem] leading-relaxed text-zaro-graphite/80">
              Custom work is what ZARO grew from. Tell us what the standard collection can&apos;t —
              and we design and build the piece in our studio, to your exact specification.
            </p>
          </Reveal>

          <Reveal delay={1}>
            <ul className="mt-8 space-y-3">
              {REASSURANCE.map((line) => (
                <li key={line} className="flex items-start gap-3 text-sm text-zaro-graphite/90">
                  <span className="mt-0.5 shrink-0 text-zaro-bronze">
                    <Check className="size-4" />
                  </span>
                  {line}
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal delay={2}>
            <div className="mt-10 border-t border-zaro-graphite/10 pt-8">
              <h2 className="text-[0.7rem] font-medium uppercase tracking-[0.22em] text-zaro-stone">
                How it works
              </h2>
              <ol className="mt-6 grid grid-cols-1 gap-x-8 gap-y-7 sm:grid-cols-2">
                {PROCESS.map((step) => (
                  <li key={step.n} className="flex gap-4">
                    <span className="font-serif text-2xl font-medium text-zaro-bronze-dark">{step.n}</span>
                    <div>
                      <h3 className="font-serif text-lg font-medium text-zaro-black">{step.title}</h3>
                      <p className="mt-1.5 text-sm leading-relaxed text-zaro-steel">{step.copy}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </Reveal>
        </div>

        <Reveal delay={1} className="hidden lg:block">
          <div className="sticky top-28 aspect-[4/5] w-full overflow-hidden">
            <BrandPhoto name="custom-furniture" />
          </div>
        </Reveal>
      </section>

      {/* Form */}
      <section className="mx-auto max-w-[100rem] px-6 sm:px-10 lg:px-16">
        <div className="mt-20 grid grid-cols-1 gap-10 border-t border-zaro-graphite/10 pt-16 lg:grid-cols-[0.8fr_1.2fr] lg:gap-20">
          <div>
            <h2 className="font-serif text-3xl font-medium leading-[1.08] text-zaro-black">
              Start your request
            </h2>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-zaro-steel">
              No commitment — share as much as you know. A member of the studio reviews every
              request and replies with next steps.
            </p>
          </div>
          <div className="max-w-2xl">
            <CustomRequestForm />
          </div>
        </div>
      </section>
    </main>
  );
}