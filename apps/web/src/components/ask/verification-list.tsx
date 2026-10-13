import { Check, ShieldAlert, ShieldCheck, X } from "lucide-react";
import type { Ref } from "react";

import type { Claim, Verification } from "@/lib/analyst-schema";
import { cn } from "@/lib/utils";

const REMOVED_REASONS = {
  value_not_found: "no tool output holds this value",
  call_not_found: "the cited query was not found",
} as const;

function valueText(claim: Claim): string {
  return claim.unit ? `${claim.value} ${claim.unit}` : String(claim.value);
}

type VerificationListProps = {
  // The claims that passed the check.
  claims: Claim[];
  verification: Verification;
  partial: boolean;
  detailsRef: Ref<HTMLDetailsElement>;
};

export function VerificationList({
  claims,
  verification,
  partial,
  detailsRef,
}: VerificationListProps) {
  const { checked, passed, removed } = verification;
  const Shield = partial ? ShieldAlert : ShieldCheck;

  return (
    <details
      ref={detailsRef}
      open
      className={cn(
        "rounded-panel border bg-card",
        partial ? "border-caveat-line" : "border-verified-line",
      )}
    >
      <summary className="flex min-h-target cursor-pointer list-none flex-wrap items-center justify-between gap-3 px-5 py-4">
        <span className="flex items-center gap-2.5 font-bold">
          <Shield
            aria-hidden="true"
            className={cn("size-5", partial ? "text-caveat" : "text-verified")}
          />
          Verification
        </span>
        <span className="font-mono text-[13px] text-muted-foreground">
          checked {checked} · passed {passed} · removed {removed.length}
        </span>
      </summary>
      <ul className="flex flex-col px-5 pb-3">
        {claims.map((claim, index) => (
          <li
            key={index}
            className="grid grid-cols-[20px_1fr_auto] items-baseline gap-3 border-t border-line-subtle py-2.5"
          >
            <Check aria-label="Passed" className="size-4 self-center text-verified" />
            <span>{claim.text}</span>
            <strong>{valueText(claim)}</strong>
          </li>
        ))}
        {removed.map(({ claim, reason }, index) => (
          <li
            key={index}
            className="grid grid-cols-[20px_1fr_auto] items-baseline gap-3 border-t border-line-subtle py-2.5 text-caveat-text"
          >
            <X aria-label="Removed" className="size-4 self-center text-caveat" />
            <span>
              <s>{claim.text}</s>
              <span className="block text-sm">Removed: {REMOVED_REASONS[reason]}.</span>
            </span>
            <s>{valueText(claim)}</s>
          </li>
        ))}
      </ul>
    </details>
  );
}
