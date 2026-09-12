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
    default: "ZARO — Modern Furniture & Metalwork",
    template: "%s · ZARO",
  },
  description:
    "Handcrafted modern furniture and custom metalwork. Built with precision, designed with intention.",
  applicationName: "ZARO",
  keywords: [
    "furniture",
    "modern furniture",
    "custom furniture",
    "metalwork",
    "bespoke furniture",
    "handmade furniture",
    "dining chairs",
    "dining tables",
  ],
  creator: "ZARO Studio",
  robots: { index: true, follow: true },
  openGraph: {
    type: "website",
    locale: "en",
    url: "/",
    siteName: "ZARO",
    title: "ZARO — Modern Furniture & Metalwork",
    description:
      "Handcrafted modern furniture and custom metalwork. Built with precision, designed with intention.",
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