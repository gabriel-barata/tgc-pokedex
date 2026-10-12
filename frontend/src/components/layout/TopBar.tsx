import { Menu, Search } from "lucide-react";
import { useCallback, useId, useRef, useState } from "react";
import { Button } from "@/ui/button.tsx";
import { Brand } from "@/components/layout/Brand.tsx";
import { CardSearch } from "@/components/layout/CardSearch.tsx";
import { MainNav } from "@/components/layout/MainNav.tsx";
import { layoutStrings } from "@/strings/layout.ts";
import { useDismiss } from "@/components/layout/use-dismiss.ts";

type Disclosure = "menu" | "search" | null;

export function TopBar() {
  const [open, setOpen] = useState<Disclosure>(null);
  const bar = useRef<HTMLDivElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const searchButton = useRef<HTMLButtonElement>(null);
  const navId = useId();
  const searchId = useId();

  const dismiss = useCallback(
    ({ restoreFocus }: { restoreFocus: boolean }) => {
      if (restoreFocus) (open === "menu" ? menuButton : searchButton).current?.focus();
      setOpen(null);
    },
    [open],
  );
  useDismiss(open !== null, bar, dismiss);

  function toggle(disclosure: Exclude<Disclosure, null>) {
    setOpen((current) => (current === disclosure ? null : disclosure));
  }

  return (
    <header className="sticky top-0 z-20 border-b border-border-hairline bg-surface-raised">
      <div
        ref={bar}
        className="relative mx-auto flex h-16 max-w-page items-center gap-2 px-4 sm:gap-6 sm:px-8"
      >
        <Brand />
        <Button
          ref={searchButton}
          variant="ghost"
          size="icon"
          className="ml-auto sm:hidden"
          aria-label={layoutStrings.openSearch}
          aria-expanded={open === "search"}
          aria-controls={searchId}
          onClick={() => {
            toggle("search");
          }}
        >
          <Search aria-hidden="true" />
        </Button>
        <CardSearch id={searchId} open={open === "search"} />
        <Button
          ref={menuButton}
          variant="ghost"
          size="icon"
          className="lg:hidden"
          aria-label={layoutStrings.menu}
          aria-expanded={open === "menu"}
          aria-controls={navId}
          onClick={() => {
            toggle("menu");
          }}
        >
          <Menu aria-hidden="true" />
        </Button>
        <MainNav
          id={navId}
          open={open === "menu"}
          onNavigate={() => {
            setOpen(null);
          }}
        />
      </div>
    </header>
  );
}
