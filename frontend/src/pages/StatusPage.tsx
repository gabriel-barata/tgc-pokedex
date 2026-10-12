import { LoaderCircle, RefreshCw } from "lucide-react";
import { PageTitle } from "@/components/layout/PageTitle.tsx";
import { layoutStrings } from "@/strings/layout.ts";
import { Button } from "@/ui/button.tsx";
import { Bubble } from "@/ui/motifs/Bubble.tsx";
import { RunRow } from "@/components/status/RunRow.tsx";
import { statusStrings } from "@/strings/status.ts";
import { useSyncNow, useSyncStatus } from "@/api/sync.ts";

const runsHeadingId = "sincronizacoes";

export function StatusPage() {
  const { data, status, refetch } = useSyncStatus();
  return (
    <>
      <PageTitle>{layoutStrings.status}</PageTitle>
      {status === "pending" && <p role="status">{statusStrings.loading}</p>}
      {status === "error" && (
        <div className="flex flex-col items-start gap-3">
          <Bubble className="h-12 w-16 scale-y-75" />
          <p>{statusStrings.loadError}</p>
          <Button variant="secondary" onClick={() => void refetch()}>
            {statusStrings.retry}
          </Button>
        </div>
      )}
      {status === "success" && (
        <section aria-labelledby={runsHeadingId}>
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <h2 id={runsHeadingId} className="text-heading">
              {statusStrings.runs}
            </h2>
            <SyncButton running={data.running} />
          </div>
          {data.runs.length === 0 ? (
            <p className="text-text-secondary">{statusStrings.noRuns}</p>
          ) : (
            <ul
              aria-labelledby={runsHeadingId}
              className="overflow-hidden rounded-lg border border-border-hairline bg-surface-raised"
            >
              {data.runs.map((run) => (
                <RunRow key={run.id} run={run} />
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}

function SyncButton({ running }: { running: boolean }) {
  const { mutate, isPending, isError } = useSyncNow();
  const busy = running || isPending;
  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        disabled={busy}
        className="max-lg:h-11"
        onClick={() => {
          mutate();
        }}
      >
        {busy ? (
          <LoaderCircle className="animate-spin motion-reduce:animate-none" />
        ) : (
          <RefreshCw />
        )}
        {busy ? statusStrings.syncing : statusStrings.syncNow}
      </Button>
      {isError && (
        <p role="alert" className="text-label text-danger">
          {statusStrings.syncError}
        </p>
      )}
    </div>
  );
}
