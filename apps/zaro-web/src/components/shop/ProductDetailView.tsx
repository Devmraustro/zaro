"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import FurnitureArtwork from "@/components/FurnitureArtwork";
import StockBadge from "@/components/ui/StockBadge";
import { ErrorState } from "@/components/ui/StateViews";
import { ArrowLeft, ArrowRight } from "@/components/ui/icons";
import { apiFetch } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import { mediaUrl } from "@/lib/media";
import type { Product } from "@/types/api";

interface DimensionView {
  width?: number;
  height?: number;
  depth?: number;
  unit?: string;
}

export default function ProductDetailView({
  slug,
  initialProduct,
  initialError,
}: {
  slug: string;
  initialProduct: Product | null;
  initialError: string | null;
}) {
  const [product, setProduct] = useState<Product | null>(initialProduct);
  const [error, setError] = useState<string | null>(initialError);
  const [activeImage, setActiveImage] = useState(0);

  useEffect(() => {
    if (initialProduct) return;
    let cancelled = false;
    apiFetch<Product>(`/products/${slug}`)
      .then((p) => {
        if (!cancelled) setProduct(p);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, initialProduct]);

  if (error) {
    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center">
        <ErrorState message={initialError ?? "This piece is temporarily unavailable."} />
        <Link
          href="/shop"
          className="inline-flex items-center gap-2 text-[0.72rem] font-medium uppercase tracking-[0.2em] text-zaro-bronze-dark transition-colors hover:text-zaro-graphite"
        >
          <ArrowLeft className="size-4" />
          Back to the collection
        </Link>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <div className="flex flex-col items-center" data-testid="loading-state">
          <span aria-hidden="true" className="relative flex size-8 items-center justify-center">
            <span className="absolute inset-0 animate-spin rounded-full border border-zaro-graphite/15 border-t-zaro-bronze" />
          </span>
          <p className="mt-4 text-xs uppercase tracking-[0.2em] text-zaro-steel">Preparing the piece…</p>
        </div>
      </div>
    );
  }

  const images = product.media.filter((m) => m.media_kind === "image");
  const current = images[activeImage] ?? null;
  const dimensions = product.dimensions as DimensionView | null;
  const dimText =
    dimensions && dimensions.width != null
      ? [dimensions.width, dimensions.height, dimensions.depth]
          .filter((v) => v != null)
          .join(" × ") +
        ` ${dimensions.unit ?? "cm"}`
      : null;

  const specRows: Array<[string, string]> = [];
  if (dimText) specRows.push(["Dimensions", dimText]);
  if (product.materials_spec && product.materials_spec.length > 0) {
    specRows.push([
      "Materials",
      product.materials_spec
        .map((m) => [m.name, m.grade, m.finish].filter(Boolean).join(", "))
        .join(" · "),
    ]);
  }
  if (product.production_time_days != null) {
    specRows.push(["Production time", `${product.production_time_days} days`]);
  }
  specRows.push([
    "Delivery",
    product.delivery_available ? (product.delivery_info ?? "Arranged individually") : "Not available",
  ]);

  return (
    <div className="pt-28 pb-24 sm:pt-32">
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="mb-8 flex items-center gap-2 text-[0.7rem] uppercase tracking-[0.16em] text-zaro-stone">
        <Link href="/shop" className="transition-colors hover:text-zaro-bronze">
          Collection
        </Link>
        <span aria-hidden="true" className="text-zaro-sand">
          /
        </span>
        <span className="max-w-[12rem] truncate text-zaro-graphite/80">{product.name}</span>
      </nav>

      <div className="grid grid-cols-1 gap-12 lg:grid-cols-[1.08fr_0.92fr] lg:gap-16">
        {/* Gallery */}
        <div>
          <div className="group relative aspect-[4/5] w-full overflow-hidden bg-zaro-ivory-dark">
            {current ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={mediaUrl(current.url_path)}
                alt={current.alt_text ?? product.name}
                className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.05]"
                decoding="async"
              />
            ) : (
              <FurnitureArtwork variant="piece" tone="light" watermark />
            )}
          </div>

          {images.length > 1 ? (
            <div className="mt-4 grid grid-cols-4 gap-4">
              {images.map((img, i) => (
                <button
                  key={img.id}
                  type="button"
                  onClick={() => setActiveImage(i)}
                  aria-label={`View image ${i + 1} of ${images.length}`}
                  aria-pressed={i === activeImage}
                  className={`relative aspect-[4/5] overflow-hidden border transition-colors ${
                    i === activeImage ? "border-zaro-bronze" : "border-transparent opacity-75 hover:opacity-100"
                  }`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={mediaUrl(img.url_path)}
                    alt=""
                    className="h-full w-full object-cover"
                    loading="lazy"
                    decoding="async"
                  />
                </button>
              ))}
            </div>
          ) : null}
        </div>

        {/* Info */}
        <div className="flex flex-col">
          <div className="flex items-center justify-between gap-4">
            <p className="font-mono text-[0.625rem] uppercase tracking-[0.2em] text-zaro-stone">
              {product.product_code}
            </p>
            <StockBadge status={product.stock_status} tone="solid" />
          </div>

          <h1 className="mt-4 font-serif text-3xl font-medium leading-[1.08] tracking-[-0.01em] text-zaro-black sm:text-[2.6rem]">
            {product.name}
          </h1>

          <p className="mt-5 text-2xl font-medium text-zaro-graphite">
            {formatPrice(product.selling_price_minor, product.currency)}
          </p>

          {product.description ? (
            <p className="mt-6 whitespace-pre-line text-[0.98rem] leading-relaxed text-zaro-graphite/80">
              {product.description}
            </p>
          ) : null}

          {specRows.length > 0 && (
            <dl className="mt-8 divide-y divide-zaro-graphite/10 border-y border-zaro-graphite/10">
              {specRows.map(([term, value]) => (
                <div key={term} className="flex justify-between gap-6 py-3.5 text-sm">
                  <dt className="text-zaro-stone">{term}</dt>
                  <dd className="text-end font-medium text-zaro-graphite">{value}</dd>
                </div>
              ))}
            </dl>
          )}

          {product.variants.length > 0 && (
            <div className="mt-8">
              <h2 className="text-[0.7rem] font-medium uppercase tracking-[0.2em] text-zaro-stone">
                Options
              </h2>
              <ul className="mt-3 space-y-2" data-testid="variants">
                {product.variants.map((variant) => (
                  <li
                    key={variant.id}
                    className="flex items-center justify-between gap-4 border border-zaro-graphite/12 px-4 py-3 text-sm"
                  >
                    <span>
                      {variant.label}
                      {variant.attributes ? (
                        <span className="block font-mono text-[0.625rem] uppercase tracking-[0.14em] text-zaro-stone">
                          {Object.entries(variant.attributes)
                            .map(([k, v]) => `${k}: ${v}`)
                            .join(" · ")}
                        </span>
                      ) : null}
                    </span>
                    <span className="font-medium">{formatPrice(variant.effective_price_minor, variant.currency)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-10 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/custom"
              className="inline-flex flex-1 items-center justify-center gap-2 bg-zaro-black px-8 py-3.5 text-[0.72rem] font-medium uppercase tracking-[0.18em] text-zaro-ivory transition-colors hover:bg-zaro-graphite-soft"
            >
              Request a custom version
              <ArrowRight className="size-4" />
            </Link>
            <Link
              href="/shop"
              className="inline-flex items-center justify-center border border-zaro-graphite/20 px-8 py-3.5 text-[0.72rem] font-medium uppercase tracking-[0.18em] text-zaro-graphite transition-colors hover:border-zaro-graphite"
            >
              Back to collection
            </Link>
          </div>

          <p className="mt-8 border-t border-zaro-graphite/10 pt-6 text-xs leading-relaxed text-zaro-stone">
            Every piece is designed and built in the ZARO studio. Sizes, materials and finishes
            can typically be adjusted to your space.
          </p>
        </div>
      </div>

      {/* Mobile sticky action bar */}
      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-zaro-graphite/10 bg-zaro-paper/95 px-6 py-3 backdrop-blur-md lg:hidden">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-lg font-medium text-zaro-black">
              {formatPrice(product.selling_price_minor, product.currency)}
            </p>
            <p className="text-[0.6rem] uppercase tracking-[0.16em] text-zaro-stone">
              {product.product_code}
            </p>
          </div>
          <Link
            href="/custom"
            className="inline-flex items-center gap-2 bg-zaro-black px-5 py-3 text-[0.68rem] font-medium uppercase tracking-[0.16em] text-zaro-ivory"
          >
            Customize
            <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </div>
      <div aria-hidden="true" className="h-20 lg:hidden" />
    </div>
  );
}