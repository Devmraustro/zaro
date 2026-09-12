import { existsSync } from "node:fs";
import { join } from "node:path";
import FurnitureArtwork from "@/components/FurnitureArtwork";
import { brandImage, type BrandImageKey } from "@/content/brand-images";

const EXTENSIONS = ["avif", "webp", "png", "jpg", "jpeg"] as const;

/** Absolute public path of the shipped photo for a manifest key, if present. */
function photoPath(name: string): string | null {
  for (const ext of EXTENSIONS) {
    const candidate = join(process.cwd(), "public", "images", `${name}.${ext}`);
    if (existsSync(candidate)) return `/images/${name}.${ext}`;
  }
  return null;
}

/**
 * Server-only image slot. Renders the real photograph from
 * `public/images/<name>.<ext>` when it exists; otherwise the cohesive
 * architectural line-art placeholder. Keeps every section on one art
 * direction until photography is dropped in.
 */
export default function BrandPhoto({
  name,
  className = "",
  priority = false,
}: {
  name: BrandImageKey;
  className?: string;
  priority?: boolean;
}) {
  const spec = brandImage(name);
  const src = photoPath(spec.name);

  if (!src) {
    return (
      <FurnitureArtwork
        variant={spec.art}
        tone={spec.tone}
        className={className}
        watermark
        aria-label={spec.alt}
      />
    );
  }

  return (
    <div className={`relative h-full w-full overflow-hidden ${className}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={spec.alt}
        className="h-full w-full object-cover"
        loading={priority ? "eager" : "lazy"}
        decoding="async"
      />
    </div>
  );
}