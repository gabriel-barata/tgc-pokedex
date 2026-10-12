import type { SVGProps } from "react";

export function Bubble(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" focusable="false" {...props}>
      <circle
        cx="32"
        cy="27"
        r="21"
        strokeWidth="3"
        className="fill-popplio-300 stroke-popplio-400"
      />
      <ellipse
        cx="24"
        cy="19"
        rx="6.5"
        ry="4"
        transform="rotate(-35 24 19)"
        opacity=".9"
        className="fill-white"
      />
      <circle cx="19" cy="28" r="2.2" opacity=".8" className="fill-white" />
      <path d="M29 47.5h6l-1 3.5h-4z" className="fill-popplio-400" />
      <ellipse cx="32" cy="55" rx="8" ry="5.5" className="fill-nose-300" />
      <ellipse cx="29.5" cy="53.5" rx="2.4" ry="1.4" opacity=".7" className="fill-white" />
    </svg>
  );
}
