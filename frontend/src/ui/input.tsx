import { cn } from "cn";
import type { ComponentProps } from "react";

export function Input({ className, type, ...props }: ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-10 w-full min-w-0 rounded-pill border border-border-hairline bg-surface-page px-4 text-body text-text-primary transition-colors duration-(--motion-fast) placeholder:text-text-secondary disabled:pointer-events-none disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}
