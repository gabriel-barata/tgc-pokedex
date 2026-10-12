import { Link } from "react-router";
import { Badge } from "@/ui/motifs/Badge.tsx";
import { layoutStrings } from "@/strings/layout.ts";

export function Brand() {
  return (
    <Link
      to="/"
      aria-label={layoutStrings.home}
      className="flex shrink-0 items-center gap-2.5 rounded-pill font-display text-heading font-semibold whitespace-nowrap text-text-primary no-underline"
    >
      <Badge className="size-10" />
      <span className="max-sm:hidden">
        <span className="text-text-accent">{layoutStrings.wordmarkAccent}</span>{" "}
        {layoutStrings.wordmarkRest}
      </span>
    </Link>
  );
}
