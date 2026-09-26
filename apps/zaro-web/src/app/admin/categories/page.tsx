"use client";

/**
 * Staff category management.
 *
 * Backed by the existing admin category endpoints:
 *   GET   /admin/categories            (products.read) — includes inactive
 *   POST  /admin/categories            (products.create)
 *   PATCH /admin/categories/{id}       (products.update)
 *
 * Categories are intentionally flat: no parent, no image. Deactivation is
 * preferred over deletion because products keep pointing at the category id.
 */

import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin-auth";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StateViews";
import {
  FormError,
  SectionCard,
  Field,
  inputClass,
  primaryButtonClass,
  quietButtonClass,
  secondaryButtonClass,
} from "@/components/admin/catalog/CatalogUi";
import type { AdminCategory, CategoryCreateInput, CategoryUpdateInput } from "@/types/api";

const BLANK: CategoryCreateInput = { name: "", description: "", sort_order: 0 };

export default function AdminCategoriesPage() {
  const [categories, setCategories] = useState<AdminCategory[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await adminFetch<AdminCategory[]>("/admin/categories");
      setCategories(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load categories");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <div>
        <h1 className="font-serif text-2xl font-medium text-zaro-black">Categories</h1>
        <p className="mt-1 text-sm text-zaro-steel">
          A single flat level. Deactivating hides a category from the public site without detaching its products.
        </p>
      </div>

      <div className="mt-8">
        <CreateCategoryForm onCreated={load} />
      </div>

      {error && !categories && (
        <div className="mt-6">
          <ErrorState message={error} onRetry={() => void load()} />
        </div>
      )}
      {!categories && !error && (
        <div className="mt-6">
          <LoadingState label="Loading categories" />
        </div>
      )}

      {categories && categories.length === 0 && (
        <div className="mt-8">
          <EmptyState
            title="No categories yet"
            description="Create the first category above, then products can be assigned to it."
          />
        </div>
      )}

      {categories && categories.length > 0 && (
        <ul className="mt-8 space-y-4">
          {categories.map((category) => (
            <li key={category.id}>
              <CategoryRow category={category} onChanged={load} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CreateCategoryForm({ onCreated }: { onCreated: () => Promise<void> | void }) {
  const [draft, setDraft] = useState<CategoryCreateInput>(BLANK);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      const payload: CategoryCreateInput = {
        name: draft.name.trim(),
        sort_order: draft.sort_order ?? 0,
      };
      const description = draft.description?.trim();
      if (description) payload.description = description;
      await adminFetch<AdminCategory>("/admin/categories", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setDraft(BLANK);
      setDone(true);
      await onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create category");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SectionCard
      title="New category"
      description="The slug is generated from the name and stays stable afterwards."
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Name" htmlFor="new-category-name">
            <input
              id="new-category-name"
              required
              maxLength={100}
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              placeholder="Dining tables"
              className={inputClass}
            />
          </Field>
          <Field label="Sort order" hint="Lower numbers appear first." htmlFor="new-category-sort">
            <input
              id="new-category-sort"
              type="number"
              min={0}
              max={10000}
              value={draft.sort_order ?? 0}
              onChange={(e) => setDraft({ ...draft, sort_order: Number(e.target.value) })}
              className={inputClass}
            />
          </Field>
          <Field label="Description" htmlFor="new-category-description">
            <input
              id="new-category-description"
              maxLength={2000}
              value={draft.description ?? ""}
              onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              placeholder="Optional"
              className={inputClass}
            />
          </Field>
        </div>
        <FormError message={error} />
        <div className="flex items-center gap-4">
          <button type="submit" disabled={busy || draft.name.trim() === ""} className={primaryButtonClass}>
            {busy ? "Creating…" : "Create category"}
          </button>
          {done ? (
            <span data-testid="category-created" className="text-sm text-[#3e5f3f]">
              Category created.
            </span>
          ) : null}
        </div>
      </form>
    </SectionCard>
  );
}

function CategoryRow({ category, onChanged }: { category: AdminCategory; onChanged: () => Promise<void> | void }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(category.name);
  const [description, setDescription] = useState(category.description ?? "");
  const [sortOrder, setSortOrder] = useState(category.sort_order);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEditing = () => {
    setName(category.name);
    setDescription(category.description ?? "");
    setSortOrder(category.sort_order);
    setError(null);
    setEditing(true);
  };

  const save = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload: CategoryUpdateInput = { name: name.trim(), sort_order: sortOrder };
      const trimmed = description.trim();
      // An empty box means "clear the description", not "leave it alone".
      payload.description = trimmed === "" ? null : trimmed;
      await adminFetch<AdminCategory>(`/admin/categories/${category.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setEditing(false);
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save category");
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async () => {
    setBusy(true);
    setError(null);
    try {
      await adminFetch<AdminCategory>(`/admin/categories/${category.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !category.is_active }),
      });
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update category");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SectionCard>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="font-serif text-lg font-medium text-zaro-black">{category.name}</h3>
            <span className="rounded-full border border-zaro-graphite/15 px-2.5 py-0.5 font-mono text-[0.6rem] uppercase tracking-[0.14em] text-zaro-stone">
              /{category.slug}
            </span>
            <span
              data-testid={category.is_active ? "category-active" : "category-inactive"}
              className={`rounded-full border px-2.5 py-0.5 text-[0.6rem] uppercase tracking-[0.14em] ${
                category.is_active
                  ? "text-[#3e5f3f] bg-[#eef4ea] border-[#cfdfc9]"
                  : "text-zaro-stone bg-zaro-ivory border-zaro-ivory-dark"
              }`}
            >
              {category.is_active ? "Active" : "Inactive"}
            </span>
          </div>
          <p className="mt-1.5 text-sm text-zaro-steel">
            {category.description || <span className="text-zaro-stone/60">No description</span>}
          </p>
          <p className="mt-1 text-[0.65rem] uppercase tracking-[0.14em] text-zaro-stone">
            Sort order {category.sort_order}
          </p>
        </div>
        {!editing && (
          <div className="flex items-center gap-3">
            <button type="button" disabled={busy} onClick={startEditing} className={secondaryButtonClass}>
              Edit
            </button>
            <button type="button" disabled={busy} onClick={() => void toggleActive()} className={quietButtonClass}>
              {category.is_active ? "Deactivate" : "Reactivate"}
            </button>
          </div>
        )}
      </div>

      {editing && (
        <form onSubmit={save} className="mt-5 flex flex-col gap-4 border-t border-zaro-graphite/10 pt-5">
          <div className="grid gap-4 md:grid-cols-3">
            <Field label="Name" htmlFor={`name-${category.id}`}>
              <input
                id={`name-${category.id}`}
                required
                maxLength={100}
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Sort order" htmlFor={`sort-${category.id}`}>
              <input
                id={`sort-${category.id}`}
                type="number"
                min={0}
                max={10000}
                value={sortOrder}
                onChange={(e) => setSortOrder(Number(e.target.value))}
                className={inputClass}
              />
            </Field>
            <Field label="Description" htmlFor={`desc-${category.id}`}>
              <input
                id={`desc-${category.id}`}
                maxLength={2000}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className={inputClass}
              />
            </Field>
          </div>
          <FormError message={error} />
          <div className="flex items-center gap-3">
            <button type="submit" disabled={busy} className={primaryButtonClass}>
              {busy ? "Saving…" : "Save changes"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setEditing(false)}
              className="px-4 py-2 text-[0.7rem] uppercase tracking-[0.18em] text-zaro-steel transition-colors hover:text-zaro-graphite"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {!editing && <FormError message={error} />}
    </SectionCard>
  );
}
