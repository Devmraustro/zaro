import BrandPhoto from "@/components/BrandPhoto";
import Reveal from "@/components/ui/Reveal";

const PRINCIPLES = [
  {
    index: "01",
    title: "Precision",
    copy: "Every piece is dimensioned and detailed like a drawing before material is cut.",
  },
  {
    index: "02",
    title: "Material",
    copy: "Solid timber and structural steel, specified for the piece — never substituted.",
  },
  {
    index: "03",
    title: "Craft",
    copy: "Joined, welded, ground and finished in the studio, by hand.",
  },
  {
    index: "04",
    title: "Detail",
    copy: "Joints, seams and edges are resolved — the details are the design.",
  },
];

export default function Craftsmanship() {
  return (
    <section id="craft" className="grain overflow-hidden bg-zaro-graphite">
      <div className="grid grid-cols-1 lg:grid-cols-2">
        <div className="relative min-h-[22rem] lg:min-h-full">
          <BrandPhoto name="craftsmanship" />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-gradient-to-t from-zaro-graphite/40 via-transparent to-transparent"
          />
        </div>

        <div className="flex flex-col justify-center px-6 py-20 sm:px-10 lg:px-16 lg:py-28">
          <Reveal>
            <p className="eyebrow text-zaro-bronze-light">Craftsmanship</p>
            <h2 className="mt-5 max-w-lg font-serif text-3xl font-medium leading-[1.08] text-zaro-ivory sm:text-4xl">
              Built in the studio, not on a line.
            </h2>
            <p className="mt-5 max-w-lg text-[0.98rem] leading-relaxed text-zaro-ivory/65">
              From structural metalwork to fine furniture, the same hands carry every
              piece from raw material to finished edge.
            </p>
          </Reveal>

          <ol className="mt-12 space-y-8">
            {PRINCIPLES.map((p, i) => (
              <Reveal key={p.index} delay={(i % 4) as 0 | 1 | 2 | 3}>
                <li className="grid grid-cols-[3.5rem_1fr] items-baseline gap-4 border-t border-zaro-ivory/12 pt-6 first:border-t-0 first:pt-0">
                  <span className="font-mono text-[0.6875rem] tracking-[0.2em] text-zaro-bronze-light">
                    {p.index}
                  </span>
                  <div>
                    <h3 className="font-serif text-xl font-medium text-zaro-ivory">{p.title}</h3>
                    <p className="mt-2 max-w-md text-sm leading-relaxed text-zaro-ivory/55">{p.copy}</p>
                  </div>
                </li>
              </Reveal>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}