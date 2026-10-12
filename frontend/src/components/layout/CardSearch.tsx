import { Search } from "lucide-react";
import { useEffect, useId, useRef } from "react";
import { Input } from "@/ui/input.tsx";
import { layoutStrings } from "@/strings/layout.ts";

export function CardSearch({ id, open }: { id: string; open: boolean }) {
  const inputId = useId();
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);

  return (
    <form
      id={id}
      role="search"
      data-open={open || undefined}
      className="group relative mx-auto hidden max-w-search flex-1 items-center sm:flex data-open:max-sm:absolute data-open:max-sm:inset-x-0 data-open:max-sm:top-full data-open:max-sm:flex data-open:max-sm:max-w-none data-open:max-sm:border-b data-open:max-sm:border-border-hairline data-open:max-sm:bg-surface-raised data-open:max-sm:px-4 data-open:max-sm:py-3"
      onSubmit={(event) => {
        event.preventDefault();
      }}
    >
      <label htmlFor={inputId} className="sr-only">
        {layoutStrings.searchLabel}
      </label>
      <Search
        aria-hidden="true"
        className="pointer-events-none absolute left-4 size-5 text-text-secondary group-data-open:max-sm:left-8"
      />
      <Input
        ref={input}
        id={inputId}
        type="search"
        placeholder={layoutStrings.searchPlaceholder}
        className="pl-11"
      />
    </form>
  );
}
