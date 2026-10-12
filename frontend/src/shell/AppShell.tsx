import { Outlet } from "react-router";
import { shellStrings } from "./strings.ts";
import { TopBar } from "./TopBar.tsx";

const mainId = "conteudo";

export function AppShell() {
  return (
    <>
      <a
        href={`#${mainId}`}
        className="sr-only z-30 rounded-pill bg-surface-raised px-4 py-2 shadow-md focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        {shellStrings.skipToContent}
      </a>
      <TopBar />
      <main
        id={mainId}
        tabIndex={-1}
        className="mx-auto w-full max-w-page px-4 py-4 outline-none sm:px-8 sm:py-8"
      >
        <Outlet />
      </main>
    </>
  );
}
