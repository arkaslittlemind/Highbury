import { ChevronDown } from "lucide-react";

/**
 * The sign at the end of a summary that the row opens. The details element
 * around it must have the group class.
 */
export function SummaryChevron() {
  return (
    <ChevronDown
      aria-hidden="true"
      className="size-5 shrink-0 text-muted-foreground transition-[rotate] duration-200 ease-out-strong group-open:rotate-180"
    />
  );
}
