"use client";

/**
 * ZARO product imagery slot. Renders the S3-backed photograph when a source
 * is available, and falls back to the architectural line-art placeholder on
 * "no media" AND on a broken/failed load — the card never shows a dead image
 * icon.
 *
 * Callers reserve the aspect ratio on the wrapping element (e.g.
 * `aspect-[4/5]`), so there is no layout shift while media loads. The main
 * hero (LCP) should pass `priority` to get eager loading + `fetchpriority`.
 * Gallery thumbnails pass `decorative` to be read as purely presentational.
 */

import { useState } from "react";
import FurnitureArtwork, { type ArtworkVariant } from "@/components/FurnitureArtwork";

export default function ProductImage({
  src,
  alt,
  variant = "piece",
  tone = "light",
  priority = false,
  decorative = false,
  className = "",
}: {
  src?: string | null;
  alt: string;
  variant?: ArtworkVariant;
  tone?: "light" | "dark";
  priority?: boolean;
  decorative?: boolean;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const showArtwork = !src || failed;

  if (showArtwork) {
    return (
      <FurnitureArtwork
        variant={variant}
        tone={tone}
        watermark
        ariaLabel={decorative ? undefined : alt}
      />
    );
  }

  return (
    // S3-backed product media is addressed by arbitrary signed/API URLs, so
    // next/image's optimization pipeline is not applied; the aspect ratio is
    // reserved by the caller and sources are sized at upload.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={decorative ? "" : alt}
      className={`h-full w-full object-cover ${className}`}
      loading={priority ? "eager" : "lazy"}
      fetchPriority={priority ? "high" : undefined}
      decoding="async"
      onError={() => setFailed(true)}
    />
  );
}