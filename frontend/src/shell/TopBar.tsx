import { Brand } from "./Brand.tsx";
import { CardSearch } from "./CardSearch.tsx";
import { MainNav } from "./MainNav.tsx";

export function TopBar() {
  return (
    <header className="sticky top-0 z-20 border-b border-border-hairline bg-surface-raised">
      <div className="mx-auto flex h-16 max-w-page items-center gap-6 px-4 sm:px-8">
        <Brand />
        <CardSearch />
        <MainNav />
      </div>
    </header>
  );
}
