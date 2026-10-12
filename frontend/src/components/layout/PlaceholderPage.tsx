import { PageTitle } from "@/components/layout/PageTitle.tsx";
import { layoutStrings } from "@/strings/layout.ts";

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <>
      <PageTitle>{title}</PageTitle>
      <p className="text-text-secondary">{layoutStrings.comingSoon}</p>
    </>
  );
}
