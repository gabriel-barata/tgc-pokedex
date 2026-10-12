import { NavLink } from "react-router";
import { layoutStrings } from "@/strings/layout.ts";

const links = [
  { to: "/colecoes", label: layoutStrings.collections },
  { to: "/status", label: layoutStrings.status },
] as const;

export function MainNav({
  id,
  open,
  onNavigate,
}: {
  id: string;
  open: boolean;
  onNavigate: () => void;
}) {
  return (
    <nav
      id={id}
      aria-label={layoutStrings.mainNav}
      data-open={open || undefined}
      className="hidden shrink-0 lg:flex lg:items-center lg:gap-5 max-lg:absolute max-lg:top-full max-lg:right-4 max-lg:mt-2 max-lg:min-w-56 max-lg:flex-col max-lg:rounded-lg max-lg:border max-lg:border-border-hairline max-lg:bg-surface-raised max-lg:p-2 max-lg:shadow-lg data-open:max-lg:flex sm:max-lg:right-8"
    >
      {links.map(({ to, label }) => (
        <NavLink
          key={to}
          to={to}
          onClick={onNavigate}
          className="border-transparent font-bold text-text-secondary no-underline hover:text-text-primary aria-[current=page]:border-selected-fg aria-[current=page]:text-text-primary lg:border-b-2 lg:py-1 max-lg:flex max-lg:min-h-11 max-lg:items-center max-lg:rounded-md max-lg:border-l-4 max-lg:px-3 max-lg:aria-[current=page]:bg-selected-bg max-lg:aria-[current=page]:text-selected-fg"
        >
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
