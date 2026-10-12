import { useParams } from "react-router";
import { NotFoundPage } from "../shell/NotFoundPage.tsx";
import { PlaceholderPage } from "../shell/PlaceholderPage.tsx";
import { useSets } from "./use-sets.ts";

export function SetPage() {
  const { setId } = useParams();
  const { data } = useSets();
  if (data === undefined) return null;
  const set = data.flatMap(({ sets }) => sets).find(({ id }) => id === setId);
  return set ? <PlaceholderPage title={set.name} /> : <NotFoundPage />;
}
