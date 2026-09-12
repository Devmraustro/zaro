import type { ArtworkVariant } from "@/components/FurnitureArtwork";

/**
 * ZARO image manifest.
 *
 * The site ships no photography yet, so each slot renders a designed
 * architectural line-art placeholder. To publish real photography, drop files
 * into `public/images/<name>.<ext>` and every <BrandPhoto name="..."/> slot
 * switches to the photo automatically — the pattern is a drop-in.
 */
export interface BrandImageSpec {
  name: string;
  art: ArtworkVariant;
  tone: "light" | "dark";
  alt: string;
  /** Fractional aspect ratio for crop/quality guidance. */
  ratio: string;
  usage: string;
  artDirection: string;
}

export const BRAND_IMAGES = {
  "hero-interior": {
    name: "hero-interior",
    art: "interior",
    tone: "dark",
    alt: "Modern furniture set within an architectural interior — soft natural light, warm materials",
    ratio: "16:10",
    usage: "Homepage hero, full-bleed",
    artDirection: "Editorial wide shot; muted ivory + graphite interior, dining chair & pendant light",
  },
  "chair-dining": {
    name: "chair-dining",
    art: "chair",
    tone: "light",
    alt: "Sculptural modern dining chair in elevation",
    ratio: "4:5",
    usage: "Category card / shop editorial",
    artDirection: "Studio shot on seamless ivory, raking soft light, strong shadow",
  },
  "table-dining": {
    name: "table-dining",
    art: "table",
    tone: "light",
    alt: "Modern dining table in elevation",
    ratio: "4:5",
    usage: "Category card / shop editorial",
    artDirection: "Studio shot on seamless ivory, near-front elevation, visible wood grain",
  },
  "metalwork": {
    name: "metalwork",
    art: "metalwork",
    tone: "dark",
    alt: "Hand-welded steel detail — bracket and fixture",
    ratio: "4:5",
    usage: "Category card / craftsmanship section",
    artDirection: "Macro shot of dark steel, weld line in warm light, graphite backdrop",
  },
  "custom-furniture": {
    name: "custom-furniture",
    art: "piece",
    tone: "light",
    alt: "Custom lounge furniture silhouette",
    ratio: "4:5",
    usage: "Category card / bespoke page",
    artDirection: "Sculptural silhouette, warm neutral backdrop, single soft key light",
  },
  "craftsmanship": {
    name: "craftsmanship",
    art: "workshop",
    tone: "dark",
    alt: "Craftsman welding in the studio — sparks and precision",
    ratio: "16:10",
    usage: "Craftsmanship section, full-bleed",
    artDirection: "In-studio workbench, warm sparks, graphite tones, shallow depth of field",
  },
} as const satisfies Record<string, BrandImageSpec>;

export type BrandImageKey = keyof typeof BRAND_IMAGES;

export function brandImage(key: BrandImageKey): BrandImageSpec {
  return BRAND_IMAGES[key];
}