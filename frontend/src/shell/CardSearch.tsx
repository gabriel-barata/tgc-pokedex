import { Search } from "lucide-react";
import { useId } from "react";
import { Input } from "../ui/input.tsx";
import { shellStrings } from "./strings.ts";

export function CardSearch() {
  const inputId = useId();
  return (
    <form
      role="search"
      className="relative mx-auto flex max-w-search flex-1 items-center"
      onSubmit={(event) => {
        event.preventDefault();
      }}
    >
      <label htmlFor={inputId} className="sr-only">
        {shellStrings.searchLabel}
      </label>
      <Search
        aria-hidden="true"
        className="pointer-events-none absolute left-4 size-5 text-text-secondary"
      />
      <Input
        id={inputId}
        type="search"
        placeholder={shellStrings.searchPlaceholder}
        className="pl-11"
      />
    </form>
  );
}
