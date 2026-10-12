import { Link } from "react-router";
import { setsStrings } from "@/strings/sets.ts";
import { TrackButton } from "@/components/sets/TrackButton.tsx";
import type { SetEntry } from "@/api/sets.ts";

export function SetRow({ set }: { set: SetEntry }) {
  const year = set.release_date.slice(0, 4);
  const count = setsStrings.cardCount(set.card_count);
  return (
    <li className="grid grid-cols-[2.5rem_1fr] items-center gap-x-4 gap-y-2 border-t border-border-hairline px-4 py-2.5 first:border-t-0 hover:bg-surface-sunken/40 sm:grid-cols-[2.5rem_1fr_4rem_6.5rem_11rem] sm:px-5">
      <span className="grid size-10 place-items-center overflow-hidden rounded-md border border-border-hairline bg-surface-page">
        {set.has_symbol && (
          <img src={`/api/images/sets/${set.id}/symbol`} alt="" className="size-7 object-contain" />
        )}
      </span>
      <span className="min-w-0">
        <Link
          to={`/colecoes/${set.id}`}
          className="font-bold text-text-primary no-underline hover:underline"
        >
          {set.name}
        </Link>
        <span className="block text-label text-text-secondary tabular-nums sm:hidden">
          {year} · {count}
        </span>
      </span>
      <span className="hidden text-label text-text-secondary tabular-nums sm:block">{year}</span>
      <span className="hidden text-label text-text-secondary tabular-nums sm:block">{count}</span>
      <TrackButton set={set} />
    </li>
  );
}
