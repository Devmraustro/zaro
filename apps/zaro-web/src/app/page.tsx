"use client";

import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="max-w-2xl text-center">
        <h1 className="font-serif text-5xl font-bold tracking-tight text-zaro-black md:text-7xl">
          ZARO
        </h1>
        <p className="mt-4 text-lg tracking-widest uppercase text-zaro-steel">
          Modern Furniture & Metalwork
        </p>
        <div className="mt-8 h-px w-16 bg-zaro-bronze mx-auto" />
        <p className="mt-8 text-base leading-relaxed text-zaro-steel">
          Handcrafted furniture and custom metalwork. Built with precision, designed with intention.
        </p>
        <div className="mt-10 flex gap-4 justify-center">
          <Link
            href="/shop"
            className="inline-flex items-center px-8 py-3 bg-zaro-black text-zaro-ivory text-sm font-medium tracking-wider uppercase transition-colors hover:bg-zaro-graphite"
          >
            Shop
          </Link>
          <Link
            href="/custom"
            className="inline-flex items-center px-8 py-3 border border-zaro-bronze text-zaro-bronze text-sm font-medium tracking-wider uppercase transition-colors hover:bg-zaro-bronze hover:text-zaro-ivory"
          >
            Custom Order
          </Link>
        </div>
      </div>
    </main>
  );
}
