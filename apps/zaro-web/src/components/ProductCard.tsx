import Link from "next/link";
import { mediaUrl, primaryImage } from "@/lib/media";
import { formatPrice } from "@/lib/format";
import StockBadge from "@/components/ui/StockBadge";
import FurnitureArtwork from "@/components/FurnitureArtwork";
import type { Product } from "@/types/api";

/** Re-exported for the product detail page and external callers. */
export { mediaUrl } from "@/lib/media";

export default function ProductCard({ product }: { product: Product }) {
  const cover = primaryImage(product);
  const price =
    product.variants.length > 0
      ? Math.min(...product.variants.map((v) => v.effective_price_minor))
      : product.selling_price_minor;

  return (
    <Link
      href={`/shop/${product.slug}`}
      className="group block"
      data-testid="product-card"
    >
      <div className="relative aspect-[4/5] w-full overflow-hidden bg-zaro-ivory-dark">
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={mediaUrl(cover.url_path)}
            alt={cover.alt_text ?? product.name}
            className="h-full w-full object-cover transition-transform duration-500 ease-out group-hover:scale-[1.04]"
            decoding="async"
            loading="lazy"
          />
        ) : (
          <FurnitureArtwork variant="piece" tone="light" watermark />
        )}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-zaro-black/0 transition-colors duration-300 group-hover:bg-zaro-black/[0.04]"
        />
        <div className="absolute end-3 top-3">
          <StockBadge status={product.stock_status} />
        </div>
      </div>
      <div className="pt-4">
        <h3 className="font-serif text-lg font-medium leading-snug text-zaro-black transition-colors duration-200 group-hover:text-zaro-bronze">
          {product.name}
        </h3>
        <div className="mt-1.5 flex items-baseline justify-between gap-3">
          <p className="text-sm font-medium text-zaro-graphite">{formatPrice(price, product.currency)}</p>
          <p className="font-mono text-[0.625rem] uppercase tracking-[0.14em] text-zaro-stone">
            {product.product_code}
          </p>
        </div>
      </div>
    </Link>
  );
}