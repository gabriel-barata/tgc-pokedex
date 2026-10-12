import { Link } from "react-router";
import { Ruff } from "@/ui/motifs/Ruff.tsx";
import { setsStrings } from "@/strings/sets.ts";
import type { SetEntry } from "@/api/sets.ts";

export function SetCover({ set, seriesName }: { set: SetEntry; seriesName: string }) {
  return (
    <article className="relative flex h-full flex-col overflow-hidden rounded-lg border border-border-hairline bg-surface-raised shadow-sm transition-[translate,box-shadow] duration-(--motion-fast) ease-out hover:-translate-y-0.5 hover:shadow-md has-[a:focus-visible]:outline-2 has-[a:focus-visible]:outline-offset-2 has-[a:focus-visible]:outline-focus-ring">
      <div className="relative grid h-36 place-items-center bg-surface-page px-6 pt-5 pb-7">
        {set.has_logo ? (
          <img
            src={`/api/images/sets/${set.id}/logo`}
            alt=""
            className="max-h-24 max-w-[78%] object-contain"
          />
        ) : (
          <span aria-hidden="true" className="text-center font-display text-title">
            {set.name}
          </span>
        )}
        <Ruff className="absolute inset-x-0 bottom-0 w-full rotate-180 text-surface-raised" />
      </div>
      <div className="grid gap-1 px-5 pt-2 pb-5">
        <h3 className="text-heading">
          <Link
            to={`/colecoes/${set.id}`}
            className="text-text-primary no-underline outline-none after:absolute after:inset-0"
          >
            {set.name}
          </Link>
        </h3>
        <p className="text-label text-text-secondary">
          {seriesName} · {set.release_date.slice(0, 4)} · {setsStrings.cardCount(set.card_count)}
        </p>
        {set.downloading && (
          <p className="text-caption text-text-secondary">{setsStrings.syncingImages}</p>
        )}
      </div>
    </article>
  );
}
