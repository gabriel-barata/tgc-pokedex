import { useId, type SVGProps } from "react";

export function Ruff(props: SVGProps<SVGSVGElement>) {
  const patternId = useId();
  return (
    <svg height="10" aria-hidden="true" focusable="false" {...props}>
      <defs>
        <pattern id={patternId} width="16" height="10" patternUnits="userSpaceOnUse">
          <circle cx="8" cy="0" r="6" fill="currentColor" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${patternId})`} />
    </svg>
  );
}
