"use client";

import { forwardRef, type SelectHTMLAttributes, type OptionHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "placeholder"> {
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, placeholder, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "w-full rounded border-zaro-graphite/20 bg-zaro-paper px-3 py-2 text-zaro-graphite placeholder:text-zaro-graphite/40 focus:border-zaro-bronze focus:outline-none focus:ring-1 focus:ring-zaro-bronze disabled:opacity-50 disabled:cursor-not-allowed transition-colors",
        className,
      )}
      {...props}
    >
      {placeholder && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {children}
    </select>
  ),
);
Select.displayName = "Select";

export const Option = forwardRef<HTMLOptionElement, OptionHTMLAttributes<HTMLOptionElement>>(
  ({ className, children, ...props }, ref) => (
    <option ref={ref} className={cn("text-zaro-graphite", className)} {...props}>
      {children}
    </option>
  ),
);
Option.displayName = "Option";