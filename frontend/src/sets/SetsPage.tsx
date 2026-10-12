import { type ReactNode, type Ref, useRef } from "react";
import { PageTitle } from "../shell/PageTitle.tsx";
import { shellStrings } from "../shell/strings.ts";
import { Button } from "../ui/button.tsx";
import { Bubble } from "../ui/motifs/Bubble.tsx";
import { Crest } from "../ui/motifs/Crest.tsx";
import { Ruff } from "../ui/motifs/Ruff.tsx";
import { SetCover } from "./SetCover.tsx";
import { SetRow } from "./SetRow.tsx";
import { setsStrings } from "./strings.ts";
import { type SeriesEntry, useSets } from "./use-sets.ts";

const trackedHeadingId = "acompanhando";
const allHeadingId = "todas-as-colecoes";

export function SetsPage() {
  const { data, status, refetch } = useSets();
  return (
    <>
      <PageTitle>{shellStrings.collections}</PageTitle>
      {status === "pending" && <p role="status">{setsStrings.loading}</p>}
      {status === "error" && (
        <div className="flex flex-col items-start gap-3">
          <Bubble className="h-12 w-16 scale-y-75" />
          <p>{setsStrings.loadError}</p>
          <Button variant="secondary" onClick={() => void refetch()}>
            {setsStrings.retry}
          </Button>
        </div>
      )}
      {status === "success" &&
        (data.length === 0 ? (
          <p className="text-text-secondary">{setsStrings.emptyCatalog}</p>
        ) : (
          <SetSections series={data} />
        ))}
    </>
  );
}

function SetSections({ series }: { series: SeriesEntry[] }) {
  const allHeading = useRef<HTMLHeadingElement>(null);
  const tracked = series.flatMap(({ name, sets }) =>
    sets.filter((set) => set.tracked).map((set) => ({ set, seriesName: name })),
  );
  return (
    <>
      <Section headingId={trackedHeadingId} title={setsStrings.trackedSets}>
        {tracked.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-border-hairline bg-surface-raised px-6 py-8 text-center">
            <div className="flex gap-2">
              <Crest className="size-12" />
              <Bubble className="size-12" />
            </div>
            <p className="font-bold">{setsStrings.noTrackedSets}</p>
            <a
              href={`#${allHeadingId}`}
              onClick={(event) => {
                event.preventDefault();
                allHeading.current?.focus();
              }}
            >
              {setsStrings.seeAllSets}
            </a>
          </div>
        ) : (
          <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-[repeat(auto-fill,minmax(18.75rem,1fr))]">
            {tracked.map(({ set, seriesName }) => (
              <li key={set.id}>
                <SetCover set={set} seriesName={seriesName} />
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section headingId={allHeadingId} title={setsStrings.allSets} headingRef={allHeading}>
        {series.map(({ id, name, sets }) => (
          <section key={id} aria-labelledby={`serie-${id}`} className="mb-8">
            <h3 id={`serie-${id}`} className="mb-2 text-heading text-text-secondary">
              {name}
            </h3>
            <ul className="overflow-hidden rounded-lg border border-border-hairline bg-surface-raised">
              {sets.map((set) => (
                <SetRow key={set.id} set={set} />
              ))}
            </ul>
          </section>
        ))}
      </Section>
    </>
  );
}

function Section({
  headingId,
  title,
  headingRef,
  children,
}: {
  headingId: string;
  title: string;
  headingRef?: Ref<HTMLHeadingElement>;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={headingId} className="mb-12">
      <h2
        id={headingId}
        ref={headingRef}
        tabIndex={-1}
        className="text-heading outline-none focus-visible:outline-2"
      >
        {title}
      </h2>
      <Ruff className="mt-1 mb-5 w-full text-border-hairline" />
      {children}
    </section>
  );
}
