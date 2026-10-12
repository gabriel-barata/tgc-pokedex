import { Ruff } from "@/ui/motifs/Ruff.tsx";

export function PageTitle({ children }: { children: string }) {
  return (
    <>
      <h1 className="text-display">{children}</h1>
      <Ruff className="mt-2 mb-5 w-40 text-border-hairline" />
    </>
  );
}
