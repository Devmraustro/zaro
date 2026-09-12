import Link from "next/link";

/**
 * ZARO wordmark. `tone` controls the color used when placed on dark/light fields.
 */
export default function BrandMark({
  tone = "ink",
  href,
  className,
}: {
  tone?: "ink" | "light" | "bronze";
  href?: string;
  className?: string;
}) {
  const color =
    tone === "light" ? "text-zaro-ivory" : tone === "bronze" ? "text-zaro-bronze" : "text-zaro-black";
  const inner = (
    <span className={`inline-flex items-baseline gap-2 ${className ?? ""}`}>
      <span className={`font-serif text-[1.35rem] font-medium leading-none tracking-[0.18em] ${color}`}>
        ZARO
      </span>
      <span
        className={`hidden text-[0.55rem] font-medium leading-none tracking-[0.28em] uppercase sm:inline ${
          tone === "light" ? "text-zaro-ivory/60" : "text-zaro-steel"
        }`}
      >
        Studio
      </span>
    </span>
  );

  if (href) {
    return (
      <Link href={href} className="group inline-flex items-center" aria-label="ZARO — home" data-testid="brandmark">
        {inner}
      </Link>
    );
  }
  return <span data-testid="brandmark">{inner}</span>;
}