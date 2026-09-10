"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin-auth";
import { formatPrice } from "@/lib/format";
import type { AdminProduct } from "@/types/api";

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  published: "Published",
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
        <h1 className="text-2xl font-bold text-zaro-black">Products</h1>
        <Link href="/admin" className="text-xs uppercase tracking-wider text-zaro-bronze hover:underline">
          Sign out / switch account
        </Link>
      </div>

      {error && <div className="mt-6 text-sm text-red-700">{error}</div>}
      {!products && !error && <div className="mt-6 text-sm text-zaro-steel">Loading…</div>}

      {products && (
        <table className="mt-6 w-full border-collapse bg-white text-sm">
          <thead>
            <tr className="border-b border-zaro-ivory-dark text-left text-xs uppercase tracking-wider text-zaro-steel">
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Price</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {products.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-zaro-steel">
                  No products yet.
                </td>
              </tr>
            )}
            {products.map((p) => (
              <tr key={p.id} className="border-b border-zaro-ivory-dark/60">
                <td className="px-4 py-3 font-mono text-xs">{p.product_code}</td>
                <td className="px-4 py-3">{p.name}</td>
                <td className="px-4 py-3">{formatPrice(p.selling_price_minor, p.currency)}</td>
                <td className="px-4 py-3">
                  <span
                    className={
                      p.status === "published"
                        ? "text-green-700"
                        : p.status === "archived"
                          ? "text-zaro-steel"
                          : "text-amber-700"
                    }
                  >
                    {STATUS_LABELS[p.status] ?? p.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
