import { PageTitle } from "./PageTitle.tsx";
import { shellStrings } from "./strings.ts";

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <>
      <PageTitle>{title}</PageTitle>
      <p className="text-text-secondary">{shellStrings.comingSoon}</p>
    </>
  );
}
