import { Ban, TriangleAlert } from "lucide-react";

import { RateLimitCard } from "@/components/ask/rate-limit-card";
import { StateCard } from "@/components/ask/state-card";
import { Button } from "@/components/ui/button";
import { retryOffer, type Turn } from "@/lib/ask-state";
import type { AskFailure } from "@/lib/ask-stream";

const UNEXPECTED = "Something went wrong. Try again.";
const PRIMARY = "min-h-target px-4.5 text-base font-semibold";
const SECONDARY = "min-h-target px-4.5 text-base dark:bg-transparent";

type FailureCardProps = {
  turn: Turn;
  failure: AskFailure;
  // The time of performance.now() when the failure came.
  failedAt: number;
  // Send the question again, in its conversation as it is now.
  onRetry: () => void;
  onAskAsNew: () => void;
  onEdit: () => void;
};

function title(failure: AskFailure): string {
  switch (failure.kind) {
    case "agent":
      return failure.message;
    case "unreachable":
      return "The analyst API is not reachable.";
    case "http":
      return failure.message ?? UNEXPECTED;
    default:
      return UNEXPECTED;
  }
}

/** The card for a turn that gave no answer. */
export function FailureCard({
  turn,
  failure,
  failedAt,
  onRetry,
  onAskAsNew,
  onEdit,
}: FailureCardProps) {
  if (failure.kind === "rate_limited") {
    return (
      <RateLimitCard
        detail={failure.detail}
        retryAfterSeconds={failure.retryAfterSeconds}
        failedAt={failedAt}
        onRetry={onRetry}
      />
    );
  }

  const edit = (
    <Button variant="outline" onClick={onEdit} className={SECONDARY}>
      Edit question
    </Button>
  );

  if (failure.kind === "conversation_ended") {
    return (
      <StateCard
        tone="neutral"
        icon={Ban}
        tag="Conversation ended"
        title="This conversation has ended."
        alert
      >
        <p className="text-foreground-2">
          The analyst no longer has the earlier questions, so it cannot answer this one as
          a follow-up.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={onAskAsNew} className={PRIMARY}>
            Ask it as a new question
          </Button>
          {edit}
        </div>
      </StateCard>
    );
  }

  const canRetry = retryOffer(turn, failure) === "same";
  return (
    <StateCard
      tone="error"
      icon={TriangleAlert}
      tag="Something went wrong"
      title={title(failure)}
      alert
    >
      <p className="text-foreground-2">
        {canRetry
          ? "No answer was shown, so no unchecked number reached you."
          : "The error ended this conversation, so the follow-up cannot go again. Start from a full question."}
      </p>
      <div className="flex flex-wrap items-center gap-3">
        {canRetry && (
          <Button onClick={onRetry} className={PRIMARY}>
            Try again
          </Button>
        )}
        {edit}
      </div>
    </StateCard>
  );
}
