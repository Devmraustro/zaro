const STOCK_LABELS: Record<string, string> = {
  in_stock: "In stock",
  made_to_order: "Made to order",
  out_of_stock: "Out of stock",
};

const STOCK_TONE: Record<string, string> = {
  in_stock: "text-[#3e5f3f] bg-[#dfe6da]",
  made_to_order: "text-zaro-bronze-dark bg-[#efe3d3]",
  out_of_stock: "text-zaro-stone bg-[#e7e4dc]",
};

/** Availability pill. Falls back to the raw status label for unknown values. */
export default function StockBadge({ status, tone = "soft" }: { status: string; tone?: "soft" | "solid" }) {
  const label = STOCK_LABELS[status] ?? status;
  const soft = STOCK_TONE[status] ?? "text-zaro-stone bg-[#e7e4dc]";
  const solid = "text-zaro-ivory bg-zaro-graphite/85";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[0.625rem] font-medium uppercase tracking-[0.14em] ${tone === "soft" ? soft : solid}`}
    >
      <span aria-hidden="true" className="inline-block size-1 rounded-full bg-current opacity-70" />
      {label}
    </span>
  );
}