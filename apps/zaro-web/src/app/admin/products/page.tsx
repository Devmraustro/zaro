"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin-auth";
import { formatPrice } from "@/lib/format";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StateViews";
import type { AdminProduct } from "@/types/api";

const STATUS_PILL: Record<string, string> = {
  draft: "text-amber-800 bg-amber-50 border-amber-200",
  active: "text-[#3e5f3f] bg-[#eef4ea] border-[#cfdfc9]",
  archived: "text-zaro-stone bg-zaro-ivory border-zaro-ivory-dark",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  active: "Published",
  archived: "Archived",
};

export default function AdminProductsPage() {
  const [products, setProducts] = useState<AdminProduct[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    adminFetch<{ items: AdminProduct[] }>("/admin/products?page_size=50")
      .then((data) => {
        if (!cancelled) setProducts(data.items);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-serif text-2xl font-medium text-zaro-black">Products</h1>
          <p className="mt-1 text-sm text-zaro-steel">Catalog overview — read-only.</p>
        </div>
        <Link
          href="/admin"
          className="text-[0.65rem] uppercase tracking-[0.2em] text-zaro-bronze-dark transition-colors hover:text-zaro-graphite"
        >
          Sign out / switch account
        </Link>
      </div>

      {error && !products && <div className="mt-6"><ErrorState message={error} /></div>}
      {!products && !error && <div className="mt-6"><LoadingState label="Loading products" /></div>}

      {products && products.length === 0 && (
        <div className="mt-6">
          <EmptyState
            title="No products yet"
            description="Once pieces are added, they appear here with price and publishing status."
          />
        </div>
      )}

      {products && products.length > 0 && (
        <div className="mt-8 overflow-x-auto border border-zaro-graphite/10 bg-zaro-paper shadow-lift">
          <table className="w-full min-w-[32rem] text-sm">
            <thead>
              <tr className="border-b border-zaro-graphite/10 text-start text-[0.625rem] uppercase tracking-[0.18em] text-zaro-stone">
                <th scope="col" className="px-5 py-3.5 text-start font-medium">Code</th>
                <th scope="col" className="px-5 py-3.5 text-start font-medium">Name</th>
                <th scope="col" className="px-5 py-3.5 text-start font-medium">Price</th>
                <th scope="col" className="px-5 py-3.5 text-start font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id} className="border-b border-zaro-graphite/5 last:border-b-0">
                  <td className="px-5 py-3.5 font-mono text-xs text-zaro-stone">{p.product_code}</td>
                  <td className="px-5 py-3.5 font-medium text-zaro-graphite">{p.name}</td>
                  <td className="px-5 py-3.5">{formatPrice(p.selling_price_minor, p.currency)}</td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`inline-block rounded-full border px-2.5 py-0.5 text-[0.625rem] uppercase tracking-[0.14em] ${STATUS_PILL[p.status] ?? STATUS_PILL.draft}`}
                    >
                      {STATUS_LABELS[p.status] ?? p.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}