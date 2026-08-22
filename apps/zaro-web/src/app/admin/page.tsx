"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { clearTokens, getAccessToken, saveTokens } from "@/lib/admin-auth";

export default function AdminLoginPage() {
  const router = useRouter();
  const [hasSession, setHasSession] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setHasSession(getAccessToken() !== null);
  }, []);

  function handleSignOut() {
    clearTokens();
    setHasSession(false);
    router.push("/admin");
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    const fd = new FormData(event.currentTarget);
    try {
      const response = await apiFetch<{ access_token: string; refresh_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: String(fd.get("email") ?? ""),
          password: String(fd.get("password") ?? ""),
        }),
      });
      saveTokens(response.access_token, response.refresh_token);
      router.push("/admin/products");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="text-2xl font-bold text-zaro-black">Sign in</h1>
      <p className="mt-2 text-zaro-steel text-sm">Staff access only.</p>

      {hasSession && (
        <div className="mt-6 border border-zaro-ivory-dark bg-white p-4 text-sm">
          <p>You have a stored session.</p>
          <div className="mt-3 flex gap-3">
            <button
              type="button"
              onClick={() => router.push("/admin/products")}
              className="bg-zaro-black px-4 py-2 text-xs uppercase tracking-wider text-zaro-ivory"
            >
              Go to products
            </button>
            <button
              type="button"
              onClick={handleSignOut}
              className="border border-zaro-ivory-dark px-4 py-2 text-xs uppercase tracking-wider"
            >
              Sign out
            </button>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-6 space-y-4" data-testid="admin-login-form">
        <label className="block">
          <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Email</span>
          <input
            name="email"
            type="email"
            required
            className="w-full border border-zaro-ivory-dark bg-white px-3 py-2 text-sm outline-none focus:border-zaro-bronze"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs uppercase tracking-wider text-zaro-steel">Password</span>
          <input
            name="password"
            type="password"
            required
            className="w-full border border-zaro-ivory-dark bg-white px-3 py-2 text-sm outline-none focus:border-zaro-bronze"
          />
        </label>
        {error && (
          <div role="alert" className="text-sm text-red-700">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-zaro-black px-8 py-3 text-sm font-medium uppercase tracking-wider text-zaro-ivory hover:bg-zaro-graphite disabled:opacity-50"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
