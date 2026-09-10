"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import { mediaUrl } from "@/components/ProductCard";
import type { Product } from "@/types/api";

const STOCK_LABELS: Record<string, string> = {
  in_stock: "In stock",
  made_to_order: "Made to order",
  out_of_stock: "Out of stock",
};

interface DimensionView {
  width?: number;
  height?: number;
  depth?: number;
  unit?: string;
}

export default function ProductDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = params?.slug;
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
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
  }, [slug]);

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <div className="text-sm text-red-700">Failed to load product: {error}</div>
        <Link href="/shop" className="mt-4 inline-block text-sm text-zaro-bronze hover:underline">
          ← Back to shop
        </Link>
      </main>
    );
  }

  if (!product) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <div className="text-sm text-zaro-steel">Loading…</div>
      </main>
    );
  }

  const images = product.media.filter((m) => m.media_kind === "image");
  const dimensions = product.dimensions as DimensionView | null;
  const dimText =
    dimensions && dimensions.width
      ? [dimensions.width, dimensions.height, dimensions.depth]
          .filter((v) => v != null)
          .join(" × ") + ` ${dimensions.unit ?? "cm"}`
      : null;

  return (
    <main className="mx-auto max-w-6xl px-6 py-16">
      <Link href="/shop" className="text-sm text-zaro-bronze hover:underline">
        ← Back to shop
      </Link>

      <div className="mt-8 grid grid-cols-1 gap-10 lg:grid-cols-2">
        <div className="space-y-4">
          {images.length > 0 ? (
            images.map((img) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={img.id}
                src={mediaUrl(img.url_path)}
                alt={img.alt_text ?? product.name}
                className="w-full border border-zaro-ivory-dark object-cover"
              />
            ))
          ) : (
            <div className="flex aspect-square w-full items-center justify-center border border-zaro-ivory-dark bg-zaro-ivory-dark font-serif text-6xl text-zaro-bronze/40">
              ZARO
            </div>
          )}
        </div>

        <div>
          <h1 className="font-serif text-4xl font-bold text-zaro-black">{product.name}</h1>
          <p className="mt-1 font-mono text-xs uppercase tracking-wider text-zaro-steel">
            {product.product_code}
          </p>

          <div className="mt-6 flex items-baseline gap-4">
            <span className="text-2xl font-semibold text-zaro-black">
              {formatPrice(product.selling_price_minor, product.currency)}
            </span>
            <span className="text-xs uppercase tracking-wider text-zaro-steel">
              {STOCK_LABELS[product.stock_status] ?? product.stock_status}
            </span>
          </div>

          {product.description && (
            <p className="mt-6 whitespace-pre-line leading-relaxed text-zaro-graphite">
              {product.description}
            </p>
          )}

          <dl className="mt-8 space-y-2 border-t border-zaro-ivory-dark pt-6 text-sm">
            {dimText && (
              <div className="flex gap-2">
                <dt className="w-40 shrink-0 text-zaro-steel">Dimensions</dt>
                <dd>{dimText}</dd>
              </div>
            )}
            {product.materials_spec && product.materials_spec.length > 0 && (
              <div className="flex gap-2">
                <dt className="w-40 shrink-0 text-zaro-steel">Materials</dt>
                <dd>
                  {product.materials_spec
                    .map((m) => [m.name, m.grade, m.finish].filter(Boolean).join(", "))
                    .join(" · ")}
                </dd>
              </div>
            )}
            {product.production_time_days != null && (
              <div className="flex gap-2">
                <dt className="w-40 shrink-0 text-zaro-steel">Production time</dt>
                <dd>{product.production_time_days} days</dd>
              </div>
            )}
            <div className="flex gap-2">
              <dt className="w-40 shrink-0 text-zaro-steel">Delivery</dt>
              <dd>
                {product.delivery_available
                  ? product.delivery_info ?? "Available — contact us for a quote"
                  : "Not available"}
              </dd>
            </div>
          </dl>

          {product.variants.length > 0 && (
            <div className="mt-8">
              <h2 className="font-serif text-lg font-semibold text-zaro-black">Variants</h2>
              <ul className="mt-3 space-y-2">
                {product.variants.map((variant) => (
                  <li
                    key={variant.id}
                    className="flex items-center justify-between border border-zaro-ivory-dark px-4 py-2 text-sm"
                  >
                    <span>
                      {variant.label}
                      {variant.attributes && (
                        <span className="ml-2 text-xs text-zaro-steel">
                          {Object.entries(variant.attributes)
                            .map(([k, v]) => `${k}: ${v}`)
                            .join(", ")}
                        </span>
                      )}
                    </span>
                    <span className="font-medium">{formatPrice(variant.effective_price_minor, variant.currency)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-10 flex gap-4">
            <Link
              href="/custom"
              className="inline-flex items-center border border-zaro-bronze px-8 py-3 text-sm font-medium uppercase tracking-wider text-zaro-bronze transition-colors hover:bg-zaro-bronze hover:text-zaro-ivory"
            >
              Request custom version
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
