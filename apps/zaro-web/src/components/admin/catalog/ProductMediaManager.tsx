"use client";

/**
 * Product media manager: upload, re-order, edit details, delete.
 *
 * Backed by the existing admin media endpoints:
 *   GET    /admin/products/{id}/media          (products.read)
 *   POST   /admin/products/{id}/media          (products.update)
 *   PATCH  /admin/products/{id}/media/{asset}  (products.update)
 *   DELETE /admin/products/{id}/media/{asset}  (products.update)
 *
 * The list is rendered from the media endpoint rather than the product payload
 * because only that route exposes original_filename / content_type / size_bytes.
 */

import { useCallback, useEffect, useState } from "react";
import { adminFetch, adminUpload } from "@/lib/admin-auth";
import { mediaUrl } from "@/lib/media";
import { EmptyState } from "@/components/ui/StateViews";
import {
  MEDIA_KIND_LABEL,
  RENDERABLE_MEDIA_KINDS,
  formatBytes,
  inputClass,
  isRenderableKind,
  mediaKindLabel,
  primaryButtonClass,
  quietButtonClass,
  type RenderableMediaKind,
} from "./CatalogUi";
import type { AdminMedia } from "@/types/api";

type EditableFields = Partial<Pick<AdminMedia, "media_kind" | "alt_text" | "sort_order">>;

export default function ProductMediaManager({
  productId,
  onError,
}: {
  productId: string;
  onError?: (message: string | null) => void;
}) {
  const [media, setMedia] = useState<AdminMedia[] | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await adminFetch<AdminMedia[]>(`/admin/products/${productId}/media`);
      setMedia(data);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "Failed to load images");
    }
  }, [productId, onError]);

  useEffect(() => {
    void load();
  }, [load]);

  const upload = useCallback(
    async (formData: FormData) => {
      setBusy(true);
      try {
        await adminUpload<AdminMedia>(`/admin/products/${productId}/media`, formData);
        await load();
      } catch (err) {
        onError?.(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setBusy(false);
      }
    },
    [productId, load, onError],
  );

  const patch = useCallback(
    async (assetId: string, fields: EditableFields) => {
      setBusy(true);
      try {
        await adminFetch<AdminMedia>(`/admin/products/${productId}/media/${assetId}`, {
          method: "PATCH",
          body: JSON.stringify(fields),
        });
        await load();
      } catch (err) {
        onError?.(err instanceof Error ? err.message : "Update failed");
      } finally {
        setBusy(false);
      }
    },
    [productId, load, onError],
  );

  const remove = useCallback(
    async (assetId: string) => {
      setBusy(true);
      try {
        await adminFetch<void>(`/admin/products/${productId}/media/${assetId}`, { method: "DELETE" });
        await load();
      } catch (err) {
        onError?.(err instanceof Error ? err.message : "Delete failed");
      } finally {
        setBusy(false);
      }
    },
    [productId, load, onError],
  );

  const move = useCallback(
    async (index: number, direction: "up" | "down") => {
      const items = media ?? [];
      const neighbor = direction === "up" ? index - 1 : index + 1;
      const current = items[index];
      const other = items[neighbor];
      if (!current || !other) return;
      // Swap sort_order values so list order persists without a renumber.
      await Promise.all([
        patch(current.id, { sort_order: other.sort_order }),
        patch(other.id, { sort_order: current.sort_order }),
      ]);
    },
    [media, patch],
  );

  const nextSortOrder = media && media.length > 0 ? Math.max(...media.map((m) => m.sort_order)) + 1 : 0;

  return (
    <div>
      <MediaUploadForm onUpload={upload} busy={busy} nextSortOrder={nextSortOrder} />

      {media === null ? (
        <p className="mt-6 text-sm text-zaro-steel">Loading images…</p>
      ) : media.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            title="No images yet"
            description="Upload the first shot above — hero and gallery images power the public product page."
          />
        </div>
      ) : (
        <ul className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
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

function MediaUploadForm({
  onUpload,
  busy,
  nextSortOrder,
}: {
  onUpload: (formData: FormData) => void;
  busy: boolean;
  nextSortOrder: number;
}) {
  const [kind, setKind] = useState<RenderableMediaKind>("gallery");
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
      data-testid="media-upload-form"
      className="flex flex-wrap items-end gap-4 rounded-sm border border-zaro-graphite/10 bg-zaro-ivory/40 p-5"
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
          onChange={(event) => setKind(event.target.value as RenderableMediaKind)}
          className={inputClass}
        >
          {RENDERABLE_MEDIA_KINDS.map((k) => (
            <option key={k} value={k}>
              {MEDIA_KIND_LABEL[k]}
            </option>
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
          className={`w-48 ${inputClass}`}
        />
      </label>
      <button type="submit" disabled={busy || file === null} className={primaryButtonClass}>
        {busy ? "Uploading…" : "Upload image"}
      </button>
      <p className="w-full text-[0.65rem] leading-relaxed text-zaro-stone/80">
        PNG, JPG or WEBP up to 5&nbsp;MB. Images are served as uploaded — resize before uploading.
      </p>
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
  onPatch: (assetId: string, fields: EditableFields) => void;
  onDelete: (assetId: string) => void;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [alt, setAlt] = useState(asset.alt_text ?? "");
  const [kind, setKind] = useState<RenderableMediaKind>(
    isRenderableKind(asset.media_kind) ? asset.media_kind : "gallery",
  );

  const saveEdit = () => {
    void onPatch(asset.id, { media_kind: kind, alt_text: alt.trim() || null });
    setEditing(false);
  };

  return (
    <li
      data-testid={`media-card-${asset.id}`}
      className="overflow-hidden rounded-sm border border-zaro-graphite/10 bg-zaro-paper shadow-lift"
    >
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
              {mediaKindLabel(asset.media_kind)}
            </span>
            <span className="text-[0.6rem] uppercase tracking-[0.14em] text-zaro-stone">#{asset.sort_order}</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={busy || index === 0}
              onClick={() => onMove(index, "up")}
              aria-label={`Move ${mediaKindLabel(asset.media_kind).toLowerCase()} image up`}
              className="rounded-sm border border-zaro-graphite/15 px-2 py-1 text-xs text-zaro-graphite transition-colors hover:bg-zaro-ivory disabled:cursor-not-allowed disabled:opacity-30"
            >
              ↑
            </button>
            <button
              type="button"
              disabled={busy || index === total - 1}
              onClick={() => onMove(index, "down")}
              aria-label={`Move ${mediaKindLabel(asset.media_kind).toLowerCase()} image down`}
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
              aria-label="Alt text"
              className={inputClass}
            />
            <select
              value={kind}
              onChange={(event) => setKind(event.target.value as RenderableMediaKind)}
              aria-label="Image kind"
              className={inputClass}
            >
              {RENDERABLE_MEDIA_KINDS.map((k) => (
                <option key={k} value={k}>
                  {MEDIA_KIND_LABEL[k]}
                </option>
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
                className={quietButtonClass}
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
