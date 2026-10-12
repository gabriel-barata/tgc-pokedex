import { NavLink } from "react-router";
import { shellStrings } from "./strings.ts";

const links = [
  { to: "/colecoes", label: shellStrings.collections },
  { to: "/status", label: shellStrings.status },
] as const;

export function MainNav() {
  return (
    <nav aria-label={shellStrings.mainNav} className="flex shrink-0 items-center gap-5">
      {links.map(({ to, label }) => (
        <NavLink
          key={to}
          to={to}
          className="border-b-2 border-transparent py-1 font-bold text-text-secondary no-underline hover:text-text-primary aria-[current=page]:border-selected-fg aria-[current=page]:text-text-primary"
        >
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
