import Link from "next/link";
import type { Product } from "@/types/api";
import { formatPrice } from "@/lib/format";

const STOCK_LABELS: Record<string, string> = {
  in_stock: "In stock",
  made_to_order: "Made to order",
  out_of_stock: "Out of stock",
};

export default function ProductCard({ product }: { product: Product }) {
  const cover = product.media.find((m) => m.media_kind === "image");
  const price =
    product.variants.length > 0
      ? Math.min(...product.variants.map((v) => v.effective_price_minor))
      : product.selling_price_minor;

  return (
    <Link
      href={`/shop/${product.slug}`}
      className="group block border border-zaro-ivory-dark bg-white transition-shadow hover:shadow-lg"
      data-testid="product-card"
    >
      <div className="aspect-square w-full overflow-hidden bg-zaro-ivory-dark">
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001"}${cover.url_path}`}
            alt={cover.alt_text ?? product.name}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center font-serif text-4xl text-zaro-bronze/40">
            ZARO
          </div>
        )}
      </div>
      <div className="p-4">
        <h3 className="font-serif text-lg font-semibold text-zaro-black group-hover:text-zaro-bronze">
          {product.name}
        </h3>
        <div className="mt-1 flex items-center justify-between">
          <span className="text-sm font-medium text-zaro-graphite">{formatPrice(price, product.currency)}</span>
          <span className="text-xs uppercase tracking-wider text-zaro-steel">
            {STOCK_LABELS[product.stock_status] ?? product.stock_status}
          </span>
        </div>
      </div>
    </Link>
  );
}
