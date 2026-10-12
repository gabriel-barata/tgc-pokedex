import { useEffect, type RefObject } from "react";

export function useDismiss(
  open: boolean,
  container: RefObject<HTMLElement | null>,
  dismiss: (options: { restoreFocus: boolean }) => void,
) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") dismiss({ restoreFocus: true });
    }
    function onPointerDown(event: PointerEvent) {
      if (!container.current?.contains(event.target as Node)) dismiss({ restoreFocus: false });
    }
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open, container, dismiss]);
}
