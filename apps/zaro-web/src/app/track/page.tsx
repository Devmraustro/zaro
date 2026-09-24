import type { Metadata } from "next";
import BrandPhoto from "@/components/BrandPhoto";
import TrackingLookup from "@/components/TrackingLookup";
import Reveal from "@/components/ui/Reveal";
import { dictFor, tr } from "@/lib/i18n";
import { getServerLang } from "@/lib/lang-server";

export const metadata: Metadata = {
  title: "Track your order",
  description:
    "Check the status of your custom furniture or metalwork request with your reference and the contact used when submitting.",
  openGraph: { title: "Track your order · ZARO", url: "/track" },
};

export default async function TrackPage() {
  const lang = await getServerLang();
  const dic = dictFor(lang);

  return (
    <main className="pb-28">
      <section className="mx-auto grid max-w-[100rem] grid-cols-1 gap-12 px-6 pt-32 sm:px-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-20 lg:px-16 lg:pt-40">
        <div className="flex flex-col justify-center">
          <Reveal>
            <p className="eyebrow text-zaro-bronze-dark">{tr(dic, "track.eyebrow")}</p>
            <h1 className="mt-5 font-serif text-4xl font-medium leading-[1.05] tracking-[-0.01em] text-zaro-black sm:text-5xl lg:text-[3.4rem]">
              {tr(dic, "track.title")}
            </h1>
            <p className="mt-6 max-w-xl text-[1rem] leading-relaxed text-zaro-graphite/80">
              {tr(dic, "track.intro")}
            </p>
          </Reveal>

          <Reveal delay={1}>
            <div className="mt-10 max-w-xl">
              <TrackingLookup />
            </div>
          </Reveal>
        </div>

        <Reveal delay={1} className="hidden lg:block">
          <div className="sticky top-28 aspect-[4/5] w-full overflow-hidden">
            <BrandPhoto name="custom-furniture" />
          </div>
        </Reveal>
      </section>
    </main>
  );
}