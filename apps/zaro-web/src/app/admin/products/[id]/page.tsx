"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { adminFetch, adminUpload } from "@/lib/admin-auth";
import { mediaUrl } from "@/lib/media";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StateViews";
import type { AdminMedia, AdminProduct } from "@/types/api";

const MEDIA_KINDS = ["hero", "gallery", "detail", "lifestyle"] as const;
type MediaKind = (typeof MEDIA_KINDS)[number];

const KIND_LABEL: Record<MediaKind, string> = {
  hero: "Hero",
  gallery: "Gallery",
  detail: "Detail",
  lifestyle: "Lifestyle",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function AdminProductMediaPage() {
  const { id } = useParams<{ id: string }>();

  const [product, setProduct] = useState<AdminProduct | null>(null);
  const [media, setMedia] = useState<AdminMedia[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [productData, mediaData] = await Promise.all([
        adminFetch<AdminProduct>(`/admin/products/${id}`),
        adminFetch<AdminMedia[]>(`/admin/products/${id}/media`),
      ]);
      setProduct(productData);
      setMedia(mediaData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load product");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const upload = useCallback(
    async (formData: FormData) => {
      setBusy(true);
      try {
        await adminUpload<AdminMedia>(`/admin/products/${id}/media`, formData);
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setBusy(false);
      }
    },
    [id, load],
  );

  const patch = useCallback(
    async (assetId: string, fields: Partial<Pick<AdminMedia, "media_kind" | "alt_text" | "sort_order">>) => {
      setBusy(true);
      try {
        await adminFetch<AdminMedia>(`/admin/products/${id}/media/${assetId}`, {
          method: "PATCH",
          body: JSON.stringify(fields),
        });
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Update failed");
      } finally {
        setBusy(false);
      }
    },
    [id, load],
  );

  const remove = useCallback(
    async (assetId: string) => {
      setBusy(true);
      try {
        await adminFetch<void>(`/admin/products/${id}/media/${assetId}`, { method: "DELETE" });
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Delete failed");
      } finally {
        setBusy(false);
      }
    },
    [id, load],
  );

  const move = useCallback(
    async (index: number, direction: "up" | "down") => {
      const items = media ?? [];
      const neighbor = direction === "up" ? index - 1 : index + 1;
      if (items[neighbor] === undefined) return;
      const current = items[index]!;
      const other = items[neighbor]!;
      // Swap sort_order values so the list order persists without a renumber.
      await Promise.all([
        patch(current.id, { sort_order: other.sort_order }),
        patch(other.id, { sort_order: current.sort_order }),
      ]);
    },
    [media, patch],
  );

  if (error && !product) {
    return (
      <div>
        <BackLink />
        <div className="mt-6"><ErrorState message={error} /></div>
      </div>
    );
  }

  if (!product || !media) {
    return (
      <div>
        <BackLink />
        <div className="mt-6"><LoadingState label="Loading product" /></div>
      </div>
    );
  }

  return (
    <div>
      <BackLink />
      <div className="mt-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-serif text-2xl font-medium text-zaro-black">{product.name}</h1>
            <span className="rounded-full border border-zaro-graphite/15 px-2.5 py-0.5 font-mono text-[0.6rem] uppercase tracking-[0.14em] text-zaro-stone">
              {product.product_code}
            </span>
          </div>
          <p className="mt-1 text-sm text-zaro-steel">
            {media.length} image{media.length === 1 ? "" : "s"} · public catalog shows images in sort order
          </p>
        </div>
      </div>

      {error && <div className="mt-4 rounded-sm border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">{error}</div>}

      <MediaUploadForm onUpload={upload} busy={busy} nextSortOrder={media.length > 0 ? media[media.length - 1]!.sort_order + 1 : 0} />

      {media.length === 0 ? (
        <div className="mt-8">
          <EmptyState
            title="No images yet"
            description="Upload the first shot above — hero + gallery images power the public product page."
          />
        </div>
      ) : (
        <ul className="mt-8 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {media.map((asset, index) => (
            <MediaCard
              key={asset.id}
              asset={asset}
              index={index}
              total={media.length}
              onMove={move}
              onPatch={patch}
              onDelete={remove}
              busy={busy}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/admin/products"
      className="text-[0.65rem] uppercase tracking-[0.2em] text-zaro-bronze-dark transition-colors hover:text-zaro-graphite"
    >
      ← Back to products
    </Link>
  );
}

function MediaUploadForm({
  onUpload,
  busy,
  nextSortOrder,
}: {
  onUpload: (formData: FormData) => void;
  busy: boolean;
  nextSortOrder: number;
}) {
  const [kind, setKind] = useState<MediaKind>("gallery");
  const [alt, setAlt] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("media_kind", kind);
    if (alt.trim()) formData.append("alt_text", alt.trim());
    formData.append("sort_order", String(nextSortOrder));
    onUpload(formData);
    setFile(null);
    setAlt("");
  };

  return (
    <form
      onSubmit={submit}
      className="mt-6 flex flex-wrap items-end gap-4 rounded-sm border border-zaro-graphite/10 bg-zaro-paper p-5 shadow-lift"
    >
      <label className="flex flex-col gap-1.5">
        <span className="text-[0.6rem] uppercase tracking-[0.18em] text-zaro-stone">Image</span>
        <input
          type="file"
          accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
          required
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          className="max-w-56 text-xs text-zaro-graphite file:mr-3 file:rounded-sm file:border-0 file:bg-zaro-ivory file:px-3 file:py-1.5 file:text-[0.65rem] file:uppercase file:tracking-[0.14em] file:text-zaro-graphite hover:file:bg-zaro-ivory-dark"
        />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-[0.6rem] uppercase tracking-[0.18em] text-zaro-stone">Kind</span>
        <select
          value={kind}
          onChange={(event) => setKind(event.target.value as MediaKind)}
          className="rounded-sm border border-zaro-graphite/20 bg-zaro-ivory px-3 py-2 text-sm text-zaro-graphite"
        >
          {MEDIA_KINDS.map((k) => (
            <option key={k} value={k}>{KIND_LABEL[k]}</option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-[0.6rem] uppercase tracking-[0.18em] text-zaro-stone">Alt text</span>
        <input
          type="text"
          maxLength={300}
          value={alt}
          onChange={(event) => setAlt(event.target.value)}
          placeholder="Accessible description"
          className="w-48 rounded-sm border border-zaro-graphite/20 bg-zaro-ivory px-3 py-2 text-sm text-zaro-graphite placeholder:text-zaro-stone/60"
        />
      </label>
      <button
        type="submit"
        disabled={busy || file === null}
        className="bg-zaro-black px-6 py-2 text-[0.7rem] font-medium uppercase tracking-[0.18em] text-zaro-ivory transition-colors hover:bg-zaro-graphite-soft disabled:cursor-not-allowed disabled:opacity-40"
      >
        {busy ? "Uploading…" : "Upload image"}
      </button>
    </form>
  );
}

function MediaCard({
  asset,
  index,
  total,
  onMove,
  onPatch,
  onDelete,
  busy,
}: {
  asset: AdminMedia;
  index: number;
  total: number;
  onMove: (index: number, direction: "up" | "down") => void;
  onPatch: (assetId: string, fields: Partial<Pick<AdminMedia, "media_kind" | "alt_text" | "sort_order">>) => void;
  onDelete: (assetId: string) => void;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [alt, setAlt] = useState(asset.alt_text ?? "");
  const [kind, setKind] = useState<MediaKind>(
    (MEDIA_KINDS as readonly string[]).includes(asset.media_kind ?? "") ? (asset.media_kind as MediaKind) : "gallery",
  );

  const kindLabel = (MEDIA_KINDS as readonly string[]).includes(asset.media_kind ?? "")
    ? KIND_LABEL[asset.media_kind as MediaKind]
    : String(asset.media_kind ?? "gallery");

  const saveEdit = () => {
    void onPatch(asset.id, { media_kind: kind, alt_text: alt.trim() || null });
    setEditing(false);
  };

  return (
    <li className="overflow-hidden rounded-sm border border-zaro-graphite/10 bg-zaro-paper shadow-lift">
      <div className="aspect-[4/3] w-full overflow-hidden bg-zaro-ivory">
        {/* eslint-disable-next-line @next/next/no-img-element -- admin tooling, image URLs come from the API */}
        <img
          src={mediaUrl(`/api/v1/files/${asset.id}/public-content`)}
          alt={asset.alt_text ?? asset.original_filename ?? "Product image"}
          className="h-full w-full object-cover"
        />
      </div>
      <div className="flex flex-col gap-3 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-zaro-graphite/15 px-2 py-0.5 text-[0.6rem] uppercase tracking-[0.14em] text-zaro-graphite">
              {kindLabel}
            </span>
            <span className="text-[0.6rem] uppercase tracking-[0.14em] text-zaro-stone">#{asset.sort_order}</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={busy || index === 0}
              onClick={() => onMove(index, "up")}
              aria-label="Move up"
              className="rounded-sm border border-zaro-graphite/15 px-2 py-1 text-xs text-zaro-graphite transition-colors hover:bg-zaro-ivory disabled:cursor-not-allowed disabled:opacity-30"
            >
              ↑
            </button>
            <button
              type="button"
              disabled={busy || index === total - 1}
              onClick={() => onMove(index, "down")}
              aria-label="Move down"
              className="rounded-sm border border-zaro-graphite/15 px-2 py-1 text-xs text-zaro-graphite transition-colors hover:bg-zaro-ivory disabled:cursor-not-allowed disabled:opacity-30"
            >
              ↓
            </button>
          </div>
        </div>

        {editing ? (
          <div className="flex flex-col gap-2">
            <input
              type="text"
              maxLength={300}
              value={alt}
              onChange={(event) => setAlt(event.target.value)}
              placeholder="Alt text"
              className="rounded-sm border border-zaro-graphite/20 bg-zaro-ivory px-2.5 py-1.5 text-sm text-zaro-graphite"
            />
            <select
              value={kind}
              onChange={(event) => setKind(event.target.value as MediaKind)}
              className="rounded-sm border border-zaro-graphite/20 bg-zaro-ivory px-2.5 py-1.5 text-sm text-zaro-graphite"
            >
              {MEDIA_KINDS.map((k) => (
                <option key={k} value={k}>{KIND_LABEL[k]}</option>
              ))}
            </select>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={saveEdit}
                className="bg-zaro-black px-3 py-1.5 text-[0.62rem] uppercase tracking-[0.14em] text-zaro-ivory disabled:opacity-40"
              >
                Save
              </button>
              <button
                type="button"
                onClick={() => setEditing(false)}
                className="px-3 py-1.5 text-[0.62rem] uppercase tracking-[0.14em] text-zaro-steel"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            <p className="line-clamp-2 min-h-8 text-xs leading-relaxed text-zaro-steel">
              {asset.alt_text || <span className="text-zaro-stone/60">No alt text</span>}
            </p>
            <p className="text-[0.6rem] uppercase tracking-[0.14em] text-zaro-stone">
              {asset.content_type} · {formatBytes(asset.size_bytes)}
            </p>
            <div className="mt-1 flex items-center justify-between gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => setEditing(true)}
                className="text-[0.62rem] uppercase tracking-[0.14em] text-zaro-bronze-dark transition-colors hover:text-zaro-graphite disabled:opacity-40"
              >
                Edit details
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void onDelete(asset.id)}
                className="text-[0.62rem] uppercase tracking-[0.14em] text-red-700 transition-colors hover:text-red-900 disabled:opacity-40"
              >
                Delete
              </button>
            </div>
          </>
        )}
      </div>
    </li>
  );
}