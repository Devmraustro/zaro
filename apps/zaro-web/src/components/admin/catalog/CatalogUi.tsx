"use client";

/**
 * Shared catalog presentation primitives for the staff tooling.
 *
 * Status vocabulary is backend-authoritative: the API stores "active" for a
 * published product. Staff-facing copy says "Published" so the difference
 * between a draft, a live listing, and an archived record stays obvious.
 */

import type { ProductMediaKind, ProductStatus, StockStatus } from "@/types/api";

const STATUS_PILL: Record<ProductStatus, string> = {
  draft: "text-amber-800 bg-amber-50 border-amber-200",
  active: "text-[#3e5f3f] bg-[#eef4ea] border-[#cfdfc9]",
  archived: "text-zaro-stone bg-zaro-ivory border-zaro-ivory-dark",
};

const STATUS_LABELS: Record<ProductStatus, string> = {
  draft: "Draft",
  active: "Published",
  archived: "Archived",
};

export function StatusPill({ status }: { status: ProductStatus }) {
  return (
    <span
      data-testid={`status-${status}`}
      className={`inline-block rounded-full border px-2.5 py-0.5 text-[0.625rem] uppercase tracking-[0.14em] ${
        STATUS_PILL[status] ?? STATUS_PILL.draft
      }`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

const STOCK_LABELS: Record<string, string> = {
  in_stock: "In stock",
  made_to_order: "Made to order",
  out_of_stock: "Out of stock",
};

export function StockLabel({ status }: { status: StockStatus | string }) {
  return (
    <span className="text-xs text-zaro-steel">{STOCK_LABELS[status] ?? status}</span>
  );
}

export function FeaturedBadge({ featured }: { featured: boolean }) {
  if (!featured) return null;
  return (
    <span
      data-testid="featured-badge"
      title="Featured — eligible for the public featured filter"
      className="inline-block rounded-full border border-zaro-bronze/40 bg-zaro-bronze/10 px-2 py-0.5 text-[0.6rem] uppercase tracking-[0.14em] text-zaro-bronze-dark"
    >
      Featured
    </span>
  );
}

export const RENDERABLE_MEDIA_KINDS = ["hero", "gallery", "detail", "lifestyle"] as const;
export type RenderableMediaKind = (typeof RENDERABLE_MEDIA_KINDS)[number];

export const MEDIA_KIND_LABEL: Record<RenderableMediaKind, string> = {
  hero: "Hero",
  gallery: "Gallery",
  detail: "Detail",
  lifestyle: "Lifestyle",
};

export function isRenderableKind(kind: string | null | undefined): kind is RenderableMediaKind {
  return (RENDERABLE_MEDIA_KINDS as readonly string[]).includes(kind ?? "");
}

export function mediaKindLabel(kind: ProductMediaKind | string | null | undefined): string {
  if (kind === "video") return "Video";
  return isRenderableKind(kind) ? MEDIA_KIND_LABEL[kind] : "Gallery";
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function SectionCard({
  title,
  description,
  action,
  children,
  id,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  id?: string;
}) {
  return (
    <section id={id} aria-labelledby={id ? `${id}-heading` : undefined} className="border border-zaro-graphite/10 bg-zaro-paper p-6 shadow-lift">
      {(title || action) && (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            {title ? (
              <h2 id={id ? `${id}-heading` : undefined} className="font-serif text-lg font-medium text-zaro-black">
                {title}
              </h2>
            ) : null}
            {description ? <p className="mt-1 text-sm text-zaro-steel">{description}</p> : null}
          </div>
          {action}
        </div>
      )}
      <div className={title || action ? "mt-5" : undefined}>{children}</div>
    </section>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      data-testid="form-error"
      className="rounded-sm border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      {message}
    </p>
  );
}

/**
 * Labelled form field.
 *
 * When an id is supplied the caption is a real <label for> and the hint sits
 * OUTSIDE the label, so the control's accessible name stays exactly the caption
 * (nesting the hint inside would append it to the name for screen readers).
 * Without an id the children are nested so the label still wraps the control.
 */
export function Field({
  label,
  hint,
  children,
  htmlFor,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  htmlFor?: string;
}) {
  const captionClass = "text-[0.6rem] uppercase tracking-[0.18em] text-zaro-stone";
  const hintNode = hint ? (
    <span className="text-[0.65rem] leading-relaxed text-zaro-stone/80">{hint}</span>
  ) : null;

  if (htmlFor === undefined) {
    return (
      <label className="flex flex-col gap-1.5">
        <span className={captionClass}>{label}</span>
        {children}
        {hintNode}
      </label>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className={captionClass}>
        {label}
      </label>
      {children}
      {hintNode}
    </div>
  );
}

export const inputClass =
  "rounded-sm border border-zaro-graphite/20 bg-zaro-ivory px-3 py-2 text-sm text-zaro-graphite placeholder:text-zaro-stone/60 focus:border-zaro-bronze focus:outline-none";

export const primaryButtonClass =
  "bg-zaro-black px-6 py-2 text-[0.7rem] font-medium uppercase tracking-[0.18em] text-zaro-ivory transition-colors hover:bg-zaro-graphite-soft disabled:cursor-not-allowed disabled:opacity-40";

export const secondaryButtonClass =
  "border border-zaro-graphite/20 px-6 py-2 text-[0.7rem] font-medium uppercase tracking-[0.18em] text-zaro-graphite transition-colors hover:border-zaro-graphite hover:bg-zaro-graphite hover:text-zaro-ivory disabled:cursor-not-allowed disabled:opacity-40";

export const quietButtonClass =
  "text-[0.62rem] uppercase tracking-[0.14em] text-zaro-bronze-dark transition-colors hover:text-zaro-graphite disabled:cursor-not-allowed disabled:opacity-40";
