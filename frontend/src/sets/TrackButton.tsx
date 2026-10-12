import { Check, Plus } from "lucide-react";
import { Button } from "../ui/button.tsx";
import { setsStrings } from "./strings.ts";
import { type SetEntry, useTrackSet } from "./use-sets.ts";

export function TrackButton({ set }: { set: SetEntry }) {
  const { mutate, isPending, isError, variables } = useTrackSet(set.id);
  const tracked = isPending ? variables : set.tracked;
  return (
    <>
      <Button
        variant={tracked ? "selected" : "secondary"}
        aria-pressed={tracked}
        className="col-start-2 justify-self-start max-lg:h-11 sm:col-start-auto sm:justify-self-end"
        onClick={() => {
          if (!isPending) mutate(!tracked);
        }}
      >
        {tracked ? <Check /> : <Plus />}
        {tracked ? setsStrings.tracking : setsStrings.track}{" "}
        <span className="sr-only">{set.name}</span>
      </Button>
      {isError && (
        <p role="alert" className="col-span-full text-label text-danger sm:text-right">
          {setsStrings.trackError(set.name)}
        </p>
      )}
    </>
  );
}
