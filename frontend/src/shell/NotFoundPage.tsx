import { Link } from "react-router";
import { PageTitle } from "./PageTitle.tsx";
import { shellStrings } from "./strings.ts";

export function NotFoundPage() {
  return (
    <>
      <PageTitle>{shellStrings.notFound}</PageTitle>
      <Link to="/">{shellStrings.backHome}</Link>
    </>
  );
}
