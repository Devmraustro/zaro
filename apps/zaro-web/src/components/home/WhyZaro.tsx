import Reveal from "@/components/ui/Reveal";
import { Section } from "@/components/ui/Section";
import { Check } from "@/components/ui/icons";

const FACTS = [
  {
    title: "Custom made",
    copy: "Built to your measurements — a piece for the space, not a catalog item.",
  },
  {
    title: "Precision craft",
    copy: "Drawn, dimensioned and detailed before a single cut is made.",
  },
  {
    title: "Premium materials",
    copy: "Solid timber and structural steel, specified for the piece.",
  },
  {
    title: "Architectural design",
    copy: "Furniture that behaves like architecture — proportion, line and load.",
  },
];

export default function WhyZaro() {
  return (
    <Section id="about" className="py-24 sm:py-32">
      <div className="grid grid-cols-1 items-start gap-12 lg:grid-cols-[0.9fr_1.1fr]">
        <Reveal>
          <p className="eyebrow text-zaro-bronze-dark">Why ZARO</p>
          <h2 className="mt-5 font-serif text-3xl font-medium leading-[1.08] text-zaro-black sm:text-4xl">
            Furniture that behaves
            <br />
            like architecture.
          </h2>
          <p className="mt-5 max-w-md text-[0.98rem] leading-relaxed text-zaro-graphite/80">
            Every ZARO piece starts from the same place: the room it will live in.
            Proportion, material and joinery are resolved the way a building is resolved —
            then made by hand.
          </p>
        </Reveal>

        <ul className="grid grid-cols-1 gap-x-10 gap-y-px sm:grid-cols-2">
          {FACTS.map((f, i) => (
            <Reveal key={f.title} delay={(i % 2) as 0 | 1}>
              <li className="border-t border-zaro-graphite/12 py-7">
                <div className="flex items-center gap-3">
                  <span aria-hidden="true" className="flex size-6 items-center justify-center rounded-full border border-zaro-bronze/40">
                    <Check className="size-3.5 text-zaro-bronze-dark" />
                  </span>
                  <h3 className="font-serif text-xl font-medium text-zaro-black">{f.title}</h3>
                </div>
                <p className="mt-3 max-w-xs text-sm leading-relaxed text-zaro-steel">{f.copy}</p>
              </li>
            </Reveal>
          ))}
        </ul>
      </div>
    </Section>
  );
}