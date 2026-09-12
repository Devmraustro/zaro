import Link from "next/link";
import type { ReactNode } from "react";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "light";

export function buttonClass(variant: Variant = "primary", className = ""): string {
  const base =
    "group/btn inline-flex items-center justify-center gap-2 px-7 py-3 text-[0.72rem] font-medium uppercase tracking-[0.18em] transition-all duration-300 ease-out select-none";
  const styles: Record<Variant, string> = {
    primary: "bg-zaro-black text-zaro-ivory hover:bg-zaro-graphite-soft hover:shadow-lift",
    secondary: "bg-zaro-bronze text-zaro-paper hover:bg-zaro-bronze-dark hover:shadow-lift",
    outline:
      "border border-zaro-graphite/20 bg-transparent text-zaro-graphite hover:border-zaro-graphite hover:bg-zaro-graphite hover:text-zaro-ivory",
    ghost: "text-zaro-graphite hover:text-zaro-bronze",
    light: "bg-zaro-ivory text-zaro-black hover:bg-zaro-paper hover:shadow-lift",
  };
  return `${base} ${styles[variant]} ${className}`;
}

type ButtonProps = {
  variant?: Variant;
  className?: string;
  children: ReactNode;
  href?: string;
  onClick?: () => void;
  type?: "button" | "submit";
};

export default function Button({
  variant = "primary",
  className,
  children,
  href,
  onClick,
  type,
}: ButtonProps) {
  if (href) {
    return (
      <Link href={href} className={buttonClass(variant, className)}>
        {children}
      </Link>
    );
  }
  return (
    <button
      type={type ?? "button"}
      onClick={onClick}
      className={buttonClass(variant, className)}
    >
      {children}
    </button>
  );
}