import type { ProductMediaPublic } from "@/types/api";

/**
 * Resolve a media url_path into an absolute URL.
 * Guards against duplicating /api/v1 when the configured API base already
 * includes it (the url_path is server-relative, e.g. /api/v1/files/<id>).
 */
export function mediaUrl(urlPath: string): string {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001").replace(
    /\/api\/v1\/?$/,
    "",
  );
  return `${base}${urlPath}`;
}

/** Resolve the primary image media for a product (or null). */
export function primaryImage(p: { media: ProductMediaPublic[] }): ProductMediaPublic | null {
  const images = p.media.filter((m) => m.media_kind === "image");
  if (images.length === 0) return null;
  return images.reduce((a, b) => (a.sort_order <= b.sort_order ? a : b), images[0] as ProductMediaPublic);
}