"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import FurnitureArtwork, { type ArtworkVariant } from "@/components/FurnitureArtwork";
import ProductImage from "@/components/ProductImage";
import { SectionHeading } from "@/components/ui/Section";
import Reveal from "@/components/ui/Reveal";
import { mediaUrl, primaryImage } from "@/lib/media";
import { formatPrice } from "@/lib/format";
import { apiFetch } from "@/lib/api";
import { ArrowUpRight } from "@/components/ui/icons";
import type { Category, PaginatedProducts } from "@/types/api";

const VARIANT_BY_KEY: Record<string, ArtworkVariant> = {
  "chair-dining": "chair",
  "table-dining": "table",
  metalwork: "metalwork",
  "custom-furniture": "piece",
};

const ARTS: ArtworkVariant[] = ["chair", "table", "metalwork", "piece"];

const EDITORIAL_PIECES = [
  {
    key: "chair-dining",
    index: "01",
    label: "Seating",
    title: "Dining chairs, drawn from line",
    href: "/shop",
  },
  {
    key: "table-dining",
    index: "02",
    label: "Tables",
    title: "Tops on precise steel frames",
    href: "/shop",
  },
  {
    key: "metalwork",
    index: "03",
    label: "Metalwork",
    title: "Welded, ground and refined",
    href: "/custom",
  },
  {
    key: "custom-furniture",
    index: "04",
    label: "Bespoke",
    title: "Built to your spec",
    href: "/custom",
  },
];

type Slot = {
  product?: {
    name: string;
    slug: string;
    priceMinor: number;
    currency: string;
    categoryLabel: string | null;
    coverSrc: string | null;
    art: ArtworkVariant;
    index: string;
  };
  editorial?: (typeof EDITORIAL_PIECES)[number];
  className: string;
  aspect: string;
};

export default function SelectedWork() {
  const [items, setItems] = useState<Slot[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiFetch<PaginatedProducts>("/products?featured=true&page_size=4&sort=newest"),
      apiFetch<Category[]>("/categories"),
    ])
      .then(([products, categories]) => {
        if (cancelled) return;
        if (products && products.items.length > 0) {
          const byId = new Map(categories?.map((c) => [c.id, c.name]) ?? []);
          const slots: Slot[] = products.items.slice(0, 4).map((p, i) => {
            const cover = primaryImage(p);
            const price =
              p.variants.length > 0
                ? Math.min(...p.variants.map((v) => v.effective_price_minor))
                : p.selling_price_minor;
            return {
              product: {
                name: p.name,
                slug: p.slug,
                priceMinor: price,
                currency: p.currency,
                categoryLabel: p.category_id ? (byId.get(p.category_id) ?? null) : null,
                coverSrc: cover ? mediaUrl(cover.url_path) : null,
                art: ARTS[i % ARTS.length] ?? "chair",
                index: String(i + 1).padStart(2, "0"),
              },
              className: SLOTS[i % SLOTS.length]?.className ?? "",
              aspect: SLOTS[i % SLOTS.length]?.aspect ?? "aspect-[4/5]",
            };
          });
          setItems(slots);
        } else {
          setItems(
            EDITORIAL_PIECES.map((e, i) => ({
              editorial: e,
              className: SLOTS[i % SLOTS.length]?.className ?? "",
              aspect: SLOTS[i % SLOTS.length]?.aspect ?? "aspect-[4/5]",
            })),
          );
        }
      })
      .catch(() => {
        if (!cancelled) {
          setItems(
            EDITORIAL_PIECES.map((e, i) => ({
              editorial: e,
              className: SLOTS[i % SLOTS.length]?.className ?? "",
              aspect: SLOTS[i % SLOTS.length]?.aspect ?? "aspect-[4/5]",
            })),
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section id="work" className="py-24 sm:py-32">
      <div className="mx-auto max-w-[100rem] px-6 sm:px-10 lg:px-16">
        <Reveal>
          <SectionHeading
            eyebrow="Selected work"
            title="Pieces that define the practice"
            description="Each piece is conceived in the studio, detailed like a drawing, then made once — by hand, to standard."
          />
        </Reveal>

        <div className="mt-16 grid grid-cols-12 gap-x-6 gap-y-14 sm:gap-y-16">
          {items
            ? items.map((slot, i) => <WorkSlot key={i} slot={slot} />)
            : Array.from({ length: 4 }, (_, i) => {
                const slot = SLOTS[i % SLOTS.length];
                return (
                  <div key={`s-${i}`} className={(slot?.className ?? "") as string}>
                    <div className={`${slot?.aspect ?? "aspect-[4/5]"} w-full animate-pulse bg-zaro-ivory-dark`} />
                  </div>
                );
              })}
        </div>
      </div>
    </section>
  );
}

const SLOTS = [
  { className: "col-span-12 sm:col-span-7 md:col-span-7", aspect: "aspect-[4/5] sm:aspect-[7/6]" },
  { className: "col-span-12 sm:col-span-5 md:col-span-5 sm:mt-24", aspect: "aspect-[4/5] sm:aspect-[4/5]" },
  { className: "col-span-12 sm:col-span-5 md:col-span-5", aspect: "aspect-[4/5] sm:aspect-[6/5]" },
  { className: "col-span-12 sm:col-span-7 md:col-span-7 sm:mt-24", aspect: "aspect-[4/5] sm:aspect-[7/6]" },
] as const;

function WorkSlot({ slot }: { slot: Slot }) {
  const product = slot.product;
  const editorial = slot.editorial;

if (product) {
    return (
      <Reveal className={slot.className}>
        <Link href={`/shop/${product.slug}`} className="group block">
          <figure className={`relative w-full overflow-hidden bg-zaro-ivory-dark ${slot.aspect}`}>
            <ProductImage
              src={product.coverSrc}
              alt={product.name}
              variant={product.art}
              className="transition-transform duration-700 ease-out group-hover:scale-[1.035]"
            />
          </figure>
          <figcaption className="mt-5 flex items-start justify-between gap-4">
            <div>
              <p className="font-mono text-[0.625rem] uppercase tracking-[0.2em] text-zaro-stone">
                {product.index} — {product.categoryLabel ?? "ZARO studio"}
              </p>
              <h3 className="mt-1.5 font-serif text-2xl font-medium leading-tight text-zaro-black transition-colors duration-200 group-hover:text-zaro-bronze">
                {product.name}
              </h3>
            </div>
            <div className="text-end">
              <p className="text-sm font-medium text-zaro-graphite">
                {product.priceMinor > 0
                  ? formatPrice(product.priceMinor, product.currency)
                  : "Request a quote"}
              </p>
              <ArrowUpRight className="mt-2 size-5 text-zaro-bronze transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
            </div>
          </figcaption>
        </Link>
      </Reveal>
    );
  }

  if (editorial) {
    return (
      <Reveal className={slot.className}>
        <Link href={editorial.href} className="group block">
          <figure className={`relative w-full overflow-hidden bg-zaro-ivory-dark ${slot.aspect}`}>
            <FurnitureArtwork
              variant={VARIANT_BY_KEY[editorial.key] ?? "piece"}
              tone="light"
              watermark
            />
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 bg-zaro-black/0 transition-colors duration-500 group-hover:bg-zaro-black/[0.06]"
            />
            <span className="absolute bottom-4 start-4 font-mono text-[0.625rem] tracking-[0.2em] text-zaro-graphite/60">
              {editorial.index} — {editorial.label}
            </span>
            <ArrowUpRight className="absolute end-4 top-4 size-5 text-zaro-bronze opacity-0 transition-all duration-300 group-hover:opacity-100" />
          </figure>
          <figcaption className="mt-5">
            <h3 className="font-serif text-2xl font-medium leading-tight text-zaro-black transition-colors duration-200 group-hover:text-zaro-bronze">
              {editorial.title}
            </h3>
            <p className="mt-1 text-sm text-zaro-steel">Explore the discipline</p>
          </figcaption>
        </Link>
      </Reveal>
    );
  }

  return null;
}