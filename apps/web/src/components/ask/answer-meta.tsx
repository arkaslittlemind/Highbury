import { ShieldAlert, ShieldCheck } from "lucide-react";

import type { Verification } from "@/lib/analyst-schema";
import { cn } from "@/lib/utils";

type AnswerMetaProps = {
  badge: "none" | "verified" | "partial";
  verification: Verification;
  // For example "Answered in 3.1 s · 5 steps".
  timing: string;
  onOpenVerification: () => void;
  // Absent when the answer has no tool call to show.
  onOpenWorking?: () => void;
};

/** The line under the question: the verification badge, the timing, and the way to the working. */
export function AnswerMeta({
  badge,
  verification,
  timing,
  onOpenVerification,
  onOpenWorking,
}: AnswerMetaProps) {
  const partial = badge === "partial";
  const Shield = partial ? ShieldAlert : ShieldCheck;

  return (
    <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
      {badge !== "none" && (
        <button
          type="button"
          onClick={onOpenVerification}
          className={cn(
            "inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 font-semibold",
            partial
              ? "border-caveat-line bg-caveat-bg text-caveat-strong"
              : "border-verified-line bg-verified-bg text-verified",
          )}
        >
          <Shield aria-hidden="true" className="size-4" strokeWidth={2.4} />
          {partial
            ? "Partially verified"
            : `${verification.passed} of ${verification.checked} claims verified`}
        </button>
      )}
      <span>{timing}</span>
      {onOpenWorking && (
        <button
          type="button"
          onClick={onOpenWorking}
          className="cursor-pointer text-foreground-2 underline"
        >
          Show the working
        </button>
      )}
    </div>
  );
}
