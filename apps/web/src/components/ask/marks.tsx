import type { ReactNode } from "react";

/**
 * The few signs that carry a state: a claim passed or was removed, a step
 * ended, a row opens, a caveat. They have the line of the shot map marks: each
 * shape keeps a 2 px line at each size (non-scaling-stroke).
 */

type MarkProps = {
  // Size and colour come from the caller, as for the other text.
  className?: string;
  // With a label, the mark is the name of its state; with none, the text next
  // to it says the state and the mark is hidden from a screen reader.
  "aria-label"?: string;
};

function Mark({ className, "aria-label": label, children }: MarkProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={className}
    >
      {children}
    </svg>
  );
}

export function CheckMark(props: MarkProps) {
  return (
    <Mark {...props}>
      <path d="M3.5 8.5l3 3 6-7" vectorEffect="non-scaling-stroke" />
    </Mark>
  );
}

/** The cross of an "off target" shot. */
export function CrossMark(props: MarkProps) {
  return (
    <Mark {...props}>
      <path d="M4 4l8 8M12 4l-8 8" vectorEffect="non-scaling-stroke" />
    </Mark>
  );
}

export function ChevronMark(props: MarkProps) {
  return (
    <Mark {...props}>
      <path d="M4 6l4 4 4-4" vectorEffect="non-scaling-stroke" />
    </Mark>
  );
}

export function AlertMark(props: MarkProps) {
  return (
    <Mark {...props}>
      <circle cx="8" cy="8" r="6.5" vectorEffect="non-scaling-stroke" />
      <path d="M8 4.75v3.75" vectorEffect="non-scaling-stroke" />
      <circle cx="8" cy="11.25" r="0.6" fill="currentColor" vectorEffect="non-scaling-stroke" />
    </Mark>
  );
}
