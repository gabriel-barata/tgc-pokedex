import { Link } from "react-router";
import { PageTitle } from "@/components/layout/PageTitle.tsx";
import { layoutStrings } from "@/strings/layout.ts";

export function NotFoundPage() {
  return (
    <>
      <PageTitle>{layoutStrings.notFound}</PageTitle>
      <Link to="/">{layoutStrings.backHome}</Link>
    </>
  );
}
