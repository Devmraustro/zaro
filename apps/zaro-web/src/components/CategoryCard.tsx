import Link from "next/link";
import FurnitureArtwork, { type ArtworkVariant } from "@/components/FurnitureArtwork";
import type { Category } from "@/types/api";

const VARIANT_BY_SLUG: Record<string, ArtworkVariant> = {
  chair: "chair",
  chairs: "chair",
  "dining-chairs": "chair",
  table: "table",
  tables: "table",
  "dining-tables": "table",
  metal: "metalwork",
  metalwork: "metalwork",
  custom: "piece",
  "custom-furniture": "piece",
};

export default function CategoryCard({ category }: { category: Category }) {
  const variant = VARIANT_BY_SLUG[category.slug] ?? "chair";
  return (
    <Link
      href={`/shop?category=${encodeURIComponent(category.slug)}`}
      className="group block"
      data-testid="category-card"
    >
      <div className="relative aspect-[4/5] w-full overflow-hidden">
        <FurnitureArtwork variant={variant} tone="light" watermark />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-zaro-black/0 transition-colors duration-300 group-hover:bg-zaro-black/[0.05]"
        />
      </div>
      <h3 className="mt-4 flex items-baseline justify-between font-serif text-xl font-medium text-zaro-black transition-colors group-hover:text-zaro-bronze">
        {category.name}
        <span aria-hidden="true" className="font-sans text-[0.7rem] font-medium tracking-[0.2em] text-zaro-bronze-dark uppercase">
          Explore
        </span>
      </h3>
      {category.description ? (
        <p className="mt-1.5 text-sm leading-relaxed text-zaro-steel">{category.description}</p>
      ) : null}
    </Link>
  );
}