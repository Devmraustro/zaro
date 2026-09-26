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

/**
 * Media kinds the API can emit (backend `MediaKind`):
 * "hero" | "gallery" | "detail" | "lifestyle" | "video".
 * "video" is excluded because it cannot be rendered through an <img> element.
 */
const RENDERABLE_MEDIA_KINDS = new Set(["hero", "gallery", "detail", "lifestyle"]);

/** All media for a product that can be displayed as an image, ordered by sort_order. */
export function renderableImages(media: ProductMediaPublic[]): ProductMediaPublic[] {
  return media
    .filter((m) => m.media_kind != null && RENDERABLE_MEDIA_KINDS.has(m.media_kind))
    .sort((a, b) => a.sort_order - b.sort_order);
}

/** Resolve the primary image media for a product (or null). Prefers media_kind "hero". */
export function primaryImage(p: { media: ProductMediaPublic[] }): ProductMediaPublic | null {
  const images = renderableImages(p.media);
  const first = images[0];
  if (!first) return null;
  return images.find((m) => m.media_kind === "hero") ?? first;
}