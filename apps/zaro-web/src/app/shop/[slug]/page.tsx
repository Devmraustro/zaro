import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ProductDetailView from "@/components/shop/ProductDetailView";
import { apiFetch, ApiError } from "@/lib/api";
import type { Product } from "@/types/api";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  try {
    const product = await apiFetch<Product>(`/products/${slug}`);
    return {
      title: product.name,
      description:
        product.description?.slice(0, 156) ??
        `Handcrafted ${product.product_code} by ZARO — precision-built furniture and metalwork.`,
      openGraph: { title: product.name, url: `/shop/${slug}` },
      robots: { index: true, follow: true },
    };
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    return {
      title: "Piece",
      robots: { index: false, follow: true },
    };
  }
}

export default async function ProductPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  let product: Product | null = null;
  let error: string | null = null;
  try {
    product = await apiFetch<Product>(`/products/${slug}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    const message = err instanceof Error ? err.message : "This piece is unavailable";
    error = message.startsWith("HTTP ") ? message.slice(5) : message;
  }

  return (
    <main className="pb-16">
      <div className="mx-auto max-w-[100rem] px-6 sm:px-10 lg:px-16">
        <ProductDetailView slug={slug} initialProduct={product} initialError={error} />
      </div>
    </main>
  );
}