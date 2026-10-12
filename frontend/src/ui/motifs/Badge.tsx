import type { SVGProps } from "react";
import { Bubble } from "./Bubble.tsx";
import { Crest } from "./Crest.tsx";

export function Badge(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" focusable="false" {...props}>
      <circle cx="32" cy="32" r="30" strokeWidth="2" className="fill-cream-50 stroke-cream-300" />
      <circle cx="32" cy="32" r="25" className="fill-cream-100" />
      <Crest x="4" y="9" width="39.68" height="39.68" />
      <Bubble x="27" y="13" width="37.12" height="37.12" />
    </svg>
  );
}
