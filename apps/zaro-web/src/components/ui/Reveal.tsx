"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Graceful entrance on scroll. Hidden only until the element is in view;
 * respects prefers-reduced-motion (renders content immediately).
 */
export default function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
}: {
  children: ReactNode;
  delay?: 0 | 1 | 2 | 3;
  className?: string;
  as?: "div" | "section" | "li" | "article";
}) {
  const ref = useRef<HTMLElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (media.matches) {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setVisible(true);
            observer.disconnect();
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const delayClass = delay === 0 ? "" : `reveal-delay-${delay}`;

  return (
    <Tag ref={ref as never} className={`reveal ${delayClass} ${visible ? "is-visible" : ""} ${className}`}>
      {children}
    </Tag>
  );
}