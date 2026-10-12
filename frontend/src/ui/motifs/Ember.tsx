import type { SVGProps } from "react";

export function Ember(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false" {...props}>
      <circle cx="8" cy="8" r="5" className="fill-crest-400" />
      <circle cx="8" cy="8" r="2.5" className="fill-torchic-500" />
    </svg>
  );
}
