"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { hasActiveSession, login, logout } from "@/lib/admin-auth";

const inputClass =
  "w-full border-b border-zaro-graphite/15 bg-transparent px-0.5 py-2.5 text-sm text-zaro-graphite outline-none transition-colors placeholder:text-zaro-stone focus:border-zaro-bronze";

const labelClass = "mb-2 block text-[0.65rem] font-medium uppercase tracking-[0.18em] text-zaro-stone";

export default function AdminLoginPage() {
  const router = useRouter();
  const [authState, setAuthState] = useState<"checking" | "signed_in" | "signed_out">("checking");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    hasActiveSession().then((active) => {
      if (!cancelled) setAuthState(active ? "signed_in" : "signed_out");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSignOut() {
    await logout();
    setAuthState("signed_out");
    router.push("/admin");
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    const fd = new FormData(event.currentTarget);
    try {
      await login(String(fd.get("email") ?? ""), String(fd.get("password") ?? ""));
      router.push("/admin/products");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (authState === "checking") {
    return (
      <div className="mx-auto flex min-h-[70vh] w-full max-w-md flex-col justify-center">
        <p className="eyebrow text-zaro-bronze-dark">Staff access</p>
        <h1 className="mt-4 font-serif text-3xl font-medium text-zaro-black">Sign in</h1>
        <p className="mt-2 text-sm text-zaro-steel">Checking session…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex min-h-[70vh] w-full max-w-md flex-col justify-center">
      <p className="eyebrow text-zaro-bronze-dark">Staff access</p>
      <h1 className="mt-4 font-serif text-3xl font-medium text-zaro-black">Sign in</h1>
      <p className="mt-2 text-sm text-zaro-steel">Authorized members only.</p>

      {authState === "signed_in" && (
        <div className="mt-8 border border-zaro-graphite/10 bg-zaro-paper p-5 text-sm shadow-lift">
          <p className="font-medium text-zaro-graphite">A session is already active.</p>
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              onClick={() => router.push("/admin/products")}
              className="bg-zaro-black px-5 py-2.5 text-[0.68rem] uppercase tracking-[0.16em] text-zaro-ivory transition-colors hover:bg-zaro-graphite-soft"
            >
              Go to products
            </button>
            <button
              type="button"
              onClick={() => void handleSignOut()}
              className="border border-zaro-graphite/20 px-5 py-2.5 text-[0.68rem] uppercase tracking-[0.16em] text-zaro-graphite transition-colors hover:border-zaro-graphite"
            >
              Sign out
            </button>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-8 space-y-7" data-testid="admin-login-form">
        <label className="block">
          <span className={labelClass}>Email</span>
          <input name="email" type="email" required className={inputClass} />
        </label>
        <label className="block">
          <span className={labelClass}>Password</span>
          <input name="password" type="password" required className={inputClass} />
        </label>
        {error && (
          <div role="alert" className="text-sm text-red-700">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-zaro-black px-8 py-3.5 text-[0.72rem] font-medium uppercase tracking-[0.18em] text-zaro-ivory transition-colors hover:bg-zaro-graphite-soft disabled:opacity-50"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}