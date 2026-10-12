import { Check, ChevronDown, CircleAlert, CircleX, LoaderCircle } from "lucide-react";
import { useId, useState } from "react";
import { Button } from "@/ui/button.tsx";
import { statusStrings } from "@/strings/status.ts";
import type { SyncRunEntry } from "@/api/sync.ts";

const startedFormat = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });

const statusIcons = {
  running: <LoaderCircle className="size-4 animate-spin motion-reduce:animate-none" />,
  succeeded: <Check className="size-4" />,
  partial: <CircleAlert className="size-4" />,
  failed: <CircleX className="size-4" />,
} as const;

export function RunRow({ run }: { run: SyncRunEntry }) {
  return (
    <li className="grid gap-1 border-b border-border-hairline px-4 py-3 last:border-b-0">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-bold">{statusStrings.kind[run.kind]}</span>
        <span
          className={`inline-flex items-center gap-1 ${run.status === "failed" ? "text-danger" : ""}`}
        >
          {statusIcons[run.status]}
          {statusStrings.status[run.status]}
        </span>
        <time dateTime={run.started_at} className="text-text-secondary">
          {startedFormat.format(new Date(run.started_at))}
        </time>
        {run.duration_ms !== null && (
          <span className="text-text-secondary">{statusStrings.duration(run.duration_ms)}</span>
        )}
      </p>
      {run.counts && (
        <p className="text-label text-text-secondary">
          {statusStrings.counts(run.counts.fetched, run.counts.updated, run.counts.failed)}
        </p>
      )}
      {run.error && <p className="text-label break-words text-danger">{run.error}</p>}
      {run.failures.length > 0 && <Failures failures={run.failures} />}
    </li>
  );
}

function Failures({ failures }: { failures: SyncRunEntry["failures"] }) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  return (
    <div>
      <Button
        variant="ghost"
        className="-ml-3 h-9 px-3 text-label max-lg:h-11"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => {
          setOpen(!open);
        }}
      >
        {statusStrings.showFailures(failures.length)}
        <ChevronDown
          className={`size-4 transition-transform duration-(--motion-fast) motion-reduce:transition-none ${open ? "rotate-180" : ""}`}
        />
      </Button>
      {open && (
        <ul id={listId} aria-label={statusStrings.failures} className="grid gap-1 text-label">
          {failures.map(({ kind, provider_id, reason }, index) => (
            <li key={`${provider_id}-${String(index)}`} className="break-words">
              {`${statusStrings.failureKind(kind)} ${provider_id}: ${reason}`}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
