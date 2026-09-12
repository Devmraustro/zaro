import type { Metadata } from "next";
import ShopView from "@/components/shop/ShopView";
import { apiFetch } from "@/lib/api";
import type { Category, PaginatedProducts } from "@/types/api";

export const metadata: Metadata = {
  title: "The Collection",
  description:
    "Browse the ZARO collection — modern furniture and custom metalwork, handcrafted and precision-built.",
  openGraph: { title: "The Collection · ZARO", url: "/shop" },
};

export const dynamic = "force-dynamic";

export default async function ShopPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string; sort?: string; page?: string; search?: string }>;
}) {
  const params = await searchParams;

  const query = new URLSearchParams();
  query.set("page", params.page ?? "1");
  query.set("sort", params.sort ?? "newest");
  if (params.category) query.set("category", params.category);
  if (params.search) query.set("search", params.search);

  let categories: Category[] = [];
  let data: PaginatedProducts | null = null;
  let error: string | null = null;
  try {
    [categories, data] = await Promise.all([
      apiFetch<Category[]>("/categories"),
      apiFetch<PaginatedProducts>(`/products?${query.toString()}`),
    ]);
  } catch (err) {
    error = err instanceof Error ? `HTTP ${err.message}` : "Failed to reach the catalog";
    error = error.startsWith("HTTP ") ? error.slice(5) : error;
  }

  return (
    <main className="pb-28">
      {/* Editorial band */}
      <div className="mx-auto max-w-[100rem] px-6 pt-32 pb-14 sm:px-10 sm:pt-36 lg:px-16">
        <p className="eyebrow text-zaro-bronze-dark">The collection</p>
        <h1 className="mt-5 font-serif text-4xl font-medium leading-[1.05] tracking-[-0.01em] text-zaro-black sm:text-5xl">
          Furniture &amp; metalwork
        </h1>
        <p className="mt-4 max-w-2xl text-[0.98rem] leading-relaxed text-zaro-steel">
          Every piece is designed in our studio and finished by hand. Filter the collection, or
          start from your own brief.
        </p>
      </div>

      <ShopView
        initialCategories={categories}
        initialData={data}
        initialError={error}
        requestedCategory={params.category ?? ""}
        requestedSort={params.sort ?? "newest"}
        requestedPage={params.page ? parseInt(params.page, 10) : 1}
        requestedSearch={params.search ?? ""}
      />
    </main>
  );
}