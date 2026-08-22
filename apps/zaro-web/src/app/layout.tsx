import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ZARO | Modern Furniture & Metalwork",
  description:
    "Handcrafted modern furniture and custom metalwork. Premium design, precise craftsmanship.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zaro-ivory text-zaro-graphite antialiased">{children}</body>
    </html>
  );
}
