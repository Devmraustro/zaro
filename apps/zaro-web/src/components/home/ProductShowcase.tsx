"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ProductCard from "@/components/ProductCard";
import Reveal from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/Section";
import { buttonClass } from "@/components/ui/Button";
import { apiFetch } from "@/lib/api";
import type { Category, PaginatedProducts } from "@/types/api";

const CONCEPT_CATEGORIES = [
  { label: "Tables", href: "/shop" },
  { label: "Shelves", href: "/shop" },
  { label: "Consoles", href: "/shop" },
  { label: "Decor", href: "/shop" },
  { label: "Custom pieces", href: "/custom" },
];

export default function ProductShowcase() {
  const [products, setProducts] = useState<PaginatedProducts | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiFetch<PaginatedProducts>("/products?sort=newest&page_size=8"),
      apiFetch<Category[]>("/categories"),
    ])
      .then(([p, c]) => {
        if (cancelled) return;
        setProducts(p);
        setCategories(c);
      })
      .catch(() => {
        if (cancelled) return;
        setProducts(null);
        setCategories([]);
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const categoryChips =
    categories.length > 0
      ? categories.map((c) => ({ label: c.name, href: `/shop?category=${encodeURIComponent(c.slug)}` }))
      : CONCEPT_CATEGORIES;

  return (
    <section id="products" className="grain bg-zaro-ivory py-24 sm:py-32">
      <div className="mx-auto max-w-[100rem] px-6 sm:px-10 lg:px-16">
        <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
          <Reveal>
            <SectionHeading
              eyebrow="Products"
              title="The collection"
              description="Ready-standard pieces from the studio — available with custom dimensions and finishes."
            />
          </Reveal>
          <Reveal delay={1}>
            <Link href="/shop" className={buttonClass("outline")}>
              View all products
            </Link>
          </Reveal>
        </div>

        <Reveal delay={2}>
          <ul className="mt-12 flex flex-wrap gap-x-8 gap-y-3 border-y border-zaro-graphite/10 py-5">
            {categoryChips.map((chip) => (
              <li key={chip.label}>
                <Link
                  href={chip.href}
                  className="text-[0.72rem] font-medium uppercase tracking-[0.2em] text-zaro-graphite/70 transition-colors hover:text-zaro-bronze-dark"
                >
                  {chip.label}
                </Link>
              </li>
            ))}
          </ul>
        </Reveal>

        {ready && products && products.items.length > 0 ? (
          <div className="mt-14 grid grid-cols-1 gap-x-6 gap-y-12 sm:grid-cols-2 lg:grid-cols-4">
            {products.items.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        ) : ready ? (
          <div className="mt-16 flex flex-col items-center px-6 pb-8 text-center" data-testid="empty-state">
            <span className="h-px w-12 bg-zaro-bronze" aria-hidden="true" />
            <h3 className="mt-6 font-serif text-2xl font-medium text-zaro-black">
              The collection is being prepared
            </h3>
            <p className="mt-3 max-w-md text-sm leading-relaxed text-zaro-steel">
              New pieces are being crafted in the studio. Until they arrive, most of our
              work begins as a conversation — tell us what your space needs.
            </p>
            <Link href="/custom" className={`mt-8 ${buttonClass("primary")}`}>
              Request a custom design
            </Link>
          </div>
        ) : (
          <div className="mt-16 grid grid-cols-1 gap-x-6 gap-y-12 px-0 sm:grid-cols-2 lg:grid-cols-4" aria-hidden="true">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="animate-pulse">
                <div className="aspect-[4/5] w-full bg-zaro-ivory-dark" />
                <div className="mt-4 h-5 w-2/3 bg-zaro-ivory-dark" />
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}