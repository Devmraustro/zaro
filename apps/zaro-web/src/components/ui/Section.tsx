import type { ReactNode } from "react";

export function Section({
  children,
  className = "",
  id,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} className={`mx-auto w-full max-w-[100rem] px-6 sm:px-10 lg:px-16 ${className}`}>
      {children}
    </section>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  align = "start",
  tone = "ink",
  as: Tag = "h2",
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  align?: "start" | "center";
  tone?: "ink" | "light";
  as?: "h2" | "h3";
}) {
  const alignClass = align === "center" ? "text-center items-center" : "text-start items-start";
  const titleColor = tone === "light" ? "text-zaro-ivory" : "text-zaro-black";
  const ink = tone === "light" ? "text-zaro-ivory/60" : "text-zaro-steel";

  return (
    <div className={`flex flex-col gap-4 ${alignClass}`}>
      {eyebrow ? (
        <p className={`eyebrow text-zaro-bronze-dark ${align === "center" ? "justify-center" : ""}`}>{eyebrow}</p>
      ) : null}
      <Tag
        className={`font-serif text-3xl font-medium leading-[1.08] tracking-[-0.01em] text-balance sm:text-4xl lg:text-[2.75rem] ${titleColor}`}
      >
        {title}
      </Tag>
      {description ? <p className={`max-w-2xl text-[0.95rem] leading-relaxed ${ink}`}>{description}</p> : null}
    </div>
  );
}