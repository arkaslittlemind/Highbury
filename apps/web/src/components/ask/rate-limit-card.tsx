"use client";

import { Timer } from "lucide-react";
import { useEffect, useState } from "react";

import { StateCard } from "@/components/ask/state-card";
import { Button } from "@/components/ui/button";
import { formatCountdown, secondsLeft } from "@/lib/ask-state";

type RateLimitCardProps = {
  // The text of the service. It names the wait as it was when the answer came.
  detail: string;
  // Null when the response had no readable Retry-After header.
  retryAfterSeconds: number | null;
  // The time of performance.now() when the response came.
  failedAt: number;
  onRetry: () => void;
};

function useSecondsLeft(retryAfterSeconds: number | null, failedAt: number): number {
  const [now, setNow] = useState(failedAt);
  useEffect(() => {
    if (retryAfterSeconds === null) return;
    const timer = setInterval(() => {
      const current = performance.now();
      setNow(current);
      if (secondsLeft(retryAfterSeconds, failedAt, current) === 0) clearInterval(timer);
    }, 250);
    return () => clearInterval(timer);
  }, [retryAfterSeconds, failedAt]);
  return retryAfterSeconds === null ? 0 : secondsLeft(retryAfterSeconds, failedAt, now);
}

export function RateLimitCard({ detail, retryAfterSeconds, failedAt, onRetry }: RateLimitCardProps) {
  const left = useSecondsLeft(retryAfterSeconds, failedAt);

  return (
    <StateCard
      tone="info"
      icon={Timer}
      tag="Slow down a little"
      title="You have reached the question limit for now."
      alert
    >
      <p className="text-foreground-2">
        Each answer runs a live model and database queries, so the number of questions in
        a minute has a limit for each visitor.
      </p>
      {retryAfterSeconds === null ? (
        <p className="text-foreground-2">{detail}</p>
      ) : (
        <div className="flex items-center gap-4 rounded-lg border bg-background p-4">
          {/* The card is an alert, so a number that changes would be read out each second. */}
          <span
            aria-hidden="true"
            className="font-display text-[44px] leading-none font-extrabold text-info"
          >
            {formatCountdown(left)}
          </span>
          <span className="text-[15px] text-foreground-2">
            {left > 0 ? "until you can ask again." : "You can ask again now."}
          </span>
          {left > 0 && <span className="sr-only">The wait is {retryAfterSeconds} seconds.</span>}
        </div>
      )}
      <div>
        <Button
          onClick={onRetry}
          disabled={left > 0}
          className="min-h-target px-4.5 text-base font-semibold"
        >
          Ask again
        </Button>
      </div>
    </StateCard>
  );
}
