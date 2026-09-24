import { Cairo, Fraunces, Inter, JetBrains_Mono } from "next/font/google";
import type { Metadata } from "next";
import AppShell from "@/components/AppShell";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
  weight: ["400", "500", "600"],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
  weight: ["400", "500"],
});

const cairo = Cairo({
  subsets: ["arabic"],
  variable: "--font-cairo",
  display: "swap",
  weight: ["400", "500", "700"],
});

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://zaro-zaro-web.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "ZARO — Handcrafted Furniture & Architectural Metalwork",
    template: "%s · ZARO",
  },
  description:
    "Premium handcrafted furniture and architectural metalwork. Custom tables, consoles, shelving and structures — drawn like architecture, built by hand, finished to spec.",
  applicationName: "ZARO",
  keywords: [
    "furniture",
    "custom furniture",
    "handcrafted furniture",
    "architectural metalwork",
    "custom metalwork",
    "bespoke furniture",
    "dining chairs",
    "dining tables",
    "consoles",
    "shelving",
  ],
  creator: "ZARO Studio",
  robots: { index: true, follow: true },
  openGraph: {
    type: "website",
    locale: "en",
    url: "/",
    siteName: "ZARO",
    title: "ZARO — Handcrafted Furniture & Architectural Metalwork",
    description:
      "Premium handcrafted furniture and architectural metalwork. Custom tables, consoles, shelving and structures — drawn like architecture, built by hand.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      dir="ltr"
      className={`${fraunces.variable} ${inter.variable} ${jetbrainsMono.variable} ${cairo.variable}`}
    >
      <body className="min-h-screen bg-zaro-ivory font-sans text-zaro-graphite antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}