import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ZARO — Modern Furniture & Metalwork",
    short_name: "ZARO",
    description: "Handcrafted modern furniture and custom metalwork.",
    start_url: "/",
    display: "standalone",
    background_color: "#faf7f1",
    theme_color: "#2b2b26",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}