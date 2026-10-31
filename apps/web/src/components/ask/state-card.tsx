import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

// The coloured top border and tag name the state, so the card has no icon.
const TONES = {
  caveat: { border: "border-t-caveat", tag: "text-caveat-strong" },
  neutral: { border: "border-t-faint", tag: "text-foreground-2" },
  error: { border: "border-t-brand", tag: "text-brand-soft" },
  info: { border: "border-t-info-line", tag: "text-info" },
} as const;

type StateCardProps = {
  tone: keyof typeof TONES;
  // The short name of the state, above the text.
  tag: string;
  title?: string;
  // An error must reach a screen reader at once.
  alert?: boolean;
  children?: ReactNode;
};

/** A card for a turn that gave something other than a plain answer. */
export function StateCard({ tone, tag, title, alert, children }: StateCardProps) {
  const colours = TONES[tone];
  return (
    <section
      role={alert ? "alert" : undefined}
      className={cn(
        "flex max-w-[820px] flex-col gap-4 rounded-panel border border-t-[3px] bg-card p-7",
        colours.border,
      )}
    >
      <span
        className={cn(
          "font-display text-[15px] font-bold tracking-[0.16em] uppercase",
          colours.tag,
        )}
      >
        {tag}
      </span>
      {title && <h2 className="font-display text-[32px] leading-[1.1] font-bold">{title}</h2>}
      {children}
    </section>
  );
}
