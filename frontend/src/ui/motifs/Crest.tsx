import type { SVGProps } from "react";

const feather = "M32 6C37 16 44 26 44 40C44 48 38.6 54 32 54C25.4 54 20 48 20 40C20 26 27 16 32 6Z";

export function Crest(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" focusable="false" {...props}>
      <path
        d={feather}
        className="fill-torchic-400"
        transform="rotate(-32 32 56) translate(32 56) scale(.7) translate(-32 -56)"
      />
      <path
        d={feather}
        className="fill-torchic-400"
        transform="rotate(32 32 56) translate(32 56) scale(.7) translate(-32 -56)"
      />
      <path d={feather} className="fill-torchic-500" transform="translate(0 2)" />
      <path
        d="M32 28C35 33 38 37 38 43C38 47 35.3 50 32 50C28.7 50 26 47 26 43C26 37 29 33 32 28Z"
        className="fill-crest-400"
      />
    </svg>
  );
}
