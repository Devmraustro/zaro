import Link from "next/link";
import BrandPhoto from "@/components/BrandPhoto";
import Reveal from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/Section";

const MATERIALS = [
  {
    key: "metalwork" as const,
    name: "Iron",
    copy: "Forged and welded structural pieces — frames, brackets and architectural steelwork.",
    href: "/shop",
  },
  {
    key: "table-dining" as const,
    name: "Steel",
    copy: "Precise, ground and refined steelwork for tables, consoles and shelving systems.",
    href: "/shop",
  },
  {
    key: "chair-dining" as const,
    name: "Wood",
    copy: "Solid timber, surfaced and finished — chosen for structure as much as grain.",
    href: "/shop",
  },
  {
    key: "custom-furniture" as const,
    name: "Custom finishes",
    copy: "Patina, powder-coat and custom dimensions — tailored to the piece and the room.",
    href: "/custom",
  },
];

export default function Materials() {
  return (
    <section id="materials" className="bg-zaro-paper py-24 sm:py-32">
      <div className="mx-auto max-w-[100rem] px-6 sm:px-10 lg:px-16">
        <Reveal>
          <SectionHeading
            eyebrow="Materials"
            title="Iron · Steel · Wood · Finish"
            description="Four materials, one discipline. Each is specified for its role in the piece and finished by hand."
          />
        </Reveal>

        <div className="mt-14 grid grid-cols-1 gap-x-6 gap-y-14 sm:grid-cols-2 lg:grid-cols-4">
          {MATERIALS.map((m, i) => (
            <Reveal key={m.name} delay={(i % 2) as 0 | 1}>
              <Link href={m.href} className="group block">
                <div className="relative aspect-[4/5] w-full overflow-hidden bg-zaro-ivory-dark">
                  <BrandPhoto name={m.key} />
                  <div
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-0 bg-zaro-black/0 transition-colors duration-500 group-hover:bg-zaro-black/[0.06]"
                  />
                </div>
                <h3 className="mt-4 font-serif text-xl font-medium text-zaro-black transition-colors duration-200 group-hover:text-zaro-bronze">
                  {m.name}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-zaro-steel">{m.copy}</p>
              </Link>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}