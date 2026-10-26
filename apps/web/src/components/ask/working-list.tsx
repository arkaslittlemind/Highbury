import type { Ref } from "react";

import { SummaryChevron } from "@/components/ask/summary-chevron";

import type { WorkingStep } from "@/lib/analyst-schema";

function rowCountText(count: number | null): string {
  if (count === null) return "";
  return count === 1 ? "1 row" : `${count} rows`;
}

type WorkingListProps = {
  working: WorkingStep[];
  // For example "5 tool calls · 3.1 s".
  totals: string;
  detailsRef: Ref<HTMLDetailsElement>;
};

/** The tool calls behind an answer: the SQL that ran, or the arguments of the call. */
export function WorkingList({ working, totals, detailsRef }: WorkingListProps) {
  return (
    <details ref={detailsRef} className="group rounded-panel border bg-surface-sunken">
      <summary className="flex min-h-target cursor-pointer list-none items-center gap-3 px-6 py-4.5">
        <span className="flex flex-1 flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <span className="font-display text-[22px] font-bold tracking-[0.08em] uppercase">
            Show the working
          </span>
          <span className="font-mono text-[13px] text-muted-foreground">{totals}</span>
        </span>
        <SummaryChevron />
      </summary>
      <ol className="flex flex-col px-6 pb-6 font-mono text-[13px]">
        {working.map((step, index) => (
          <li
            key={index}
            // A claim moves the focus here, so the row must show it also after a click.
            data-row={index}
            tabIndex={-1}
            className="grid grid-cols-1 items-start gap-x-4 gap-y-2 border-t border-line-subtle py-3 focus:outline-2 focus:outline-offset-2 focus:outline-ring md:grid-cols-[32px_170px_minmax(0,1fr)_auto]"
          >
            <span className="text-faint">{index + 1}</span>
            <span className="flex flex-col gap-0.5">
              <span className="text-brand-soft">{step.tool}</span>
              {step.call_id && <span className="text-faint">{step.call_id}</span>}
            </span>
            <div className="flex min-w-0 flex-col gap-2">
              {/* The service sends a statement as one line, so it must wrap to be read. */}
              <pre className="rounded-lg border border-line-subtle bg-code-bg px-4 py-3.5 leading-relaxed wrap-break-word whitespace-pre-wrap text-code">
                {step.sql ?? JSON.stringify(step.args, null, 2)}
              </pre>
              {step.error && <p className="font-sans text-sm text-brand">{step.error}</p>}
            </div>
            <span className="text-muted-foreground">{rowCountText(step.row_count)}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}
