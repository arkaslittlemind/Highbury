import { ArrowUpRight, Plus } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * The light pill of the landing screen, for a button or a link. It gets smaller
 * while it is pressed, so the visitor sees that the page took the press.
 */
export const pill =
  "group/pill inline-flex min-h-12 shrink-0 cursor-pointer items-center gap-3 rounded-full bg-paper py-1 pr-1 pl-5 font-semibold text-background transition-[scale,background-color] duration-150 ease-out hover:bg-white active:scale-[0.97]";

const ICON = "size-4 transition-[translate,rotate] duration-200 ease-out-strong";

/** The dark disc at the end of a pill. Its icon moves when the pointer is on the pill. */
export function PillDisc({ icon = "arrow" }: { icon?: "arrow" | "plus" }) {
  return (
    <span
      aria-hidden="true"
      className="flex size-10 shrink-0 items-center justify-center rounded-full bg-background text-paper"
    >
      {icon === "arrow" ? (
        <ArrowUpRight
          strokeWidth={2.2}
          className={cn(ICON, "group-hover/pill:translate-x-0.5 group-hover/pill:-translate-y-0.5")}
        />
      ) : (
        <Plus strokeWidth={2.2} className={cn(ICON, "group-hover/pill:rotate-90")} />
      )}
    </span>
  );
}
