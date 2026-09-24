import Link from "next/link";
import BrandPhoto from "@/components/BrandPhoto";
import Reveal from "@/components/ui/Reveal";
import { Section } from "@/components/ui/Section";
import { buttonClass } from "@/components/ui/Button";
import { ArrowRight } from "@/components/ui/icons";

const PROCESS = [
  { index: "01", title: "Discuss", copy: "Share your space, your measurements and the piece you need." },
  { index: "02", title: "Design", copy: "We draw the proposal, refine materials and confirm every detail." },
  { index: "03", title: "Build", copy: "The piece is made in our studio — welded, joined and finished by hand." },
  { index: "04", title: "Deliver", copy: "Delivery to your wilaya or commune, ready to live in the room it was drawn for." },
];

export default function CustomDesign() {
  return (
    <Section id="custom-design" className="py-24 sm:py-32">
      <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-[0.85fr_1.15fr]">
        <Reveal className="order-2 lg:order-1">
          <div className="relative aspect-[4/3] w-full overflow-hidden lg:aspect-[5/4]">
            <BrandPhoto name="custom-furniture" />
          </div>
        </Reveal>

        <Reveal className="order-1 lg:order-2">
          <p className="eyebrow text-zaro-bronze-dark">Custom design</p>
          <h2 className="mt-5 font-serif text-3xl font-medium leading-[1.08] text-zaro-black sm:text-5xl lg:text-[3.25rem]">
            Your idea.
            <br />
            Made real.
          </h2>
          <p className="mt-6 max-w-xl text-[0.98rem] leading-relaxed text-zaro-graphite/80">
            When the standard piece isn&apos;t enough, we build to your exact
            specification — tailored tables, shelving, consoles and structures that
            resolve a specific space. The process is the same for every commission:
          </p>

          <ol className="mt-10 grid grid-cols-1 gap-x-8 gap-y-7 sm:grid-cols-2">
            {PROCESS.map((step) => (
              <li key={step.index} className="border-t border-zaro-graphite/12 pt-5">
                <span className="font-mono text-[0.6875rem] tracking-[0.2em] text-zaro-bronze-dark">
                  {step.index}
                </span>
                <h3 className="mt-2 font-serif text-lg font-medium text-zaro-black">{step.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-zaro-steel">{step.copy}</p>
              </li>
            ))}
          </ol>

          <div className="mt-10">
            <Link href="/custom" className={buttonClass("primary")}>
              Start a project
              <ArrowRight className="size-4 transition-transform duration-300 group-hover/btn:translate-x-0.5" />
            </Link>
          </div>
        </Reveal>
      </div>
    </Section>
  );
}