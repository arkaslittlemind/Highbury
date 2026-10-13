"use client";

import { Check } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import type { Step } from "@/lib/analyst-schema";
import { formatElapsed } from "@/lib/ask-state";

type StepListProps = {
  steps: Step[];
  // The time of performance.now() when the question went out.
  startedAt: number;
  onStop: () => void;
};

function useNow(start: number): number {
  const [now, setNow] = useState(start);
  useEffect(() => {
    const timer = setInterval(() => setNow(performance.now()), 100);
    return () => clearInterval(timer);
  }, []);
  return now;
}

export function StepList({ steps, startedAt, onStop }: StepListProps) {
  const now = useNow(startedAt);
  // The service says when a tool call starts and not when it ends, so only the
  // newest step can still run.
  const running = steps.length - 1;

  return (
    <section
      aria-labelledby="steps-title"
      className="min-w-0 max-w-[460px] flex-[1_1_400px] rounded-panel border bg-card p-6"
    >
      <div className="mb-4.5 flex items-center justify-between">
        <h2
          id="steps-title"
          className="font-display text-xl font-bold tracking-[0.12em] uppercase"
        >
          Analyst at work
        </h2>
        {/* A clock in a live region would be read out ten times a second. */}
        <span aria-hidden="true" className="font-mono text-sm text-muted-foreground">
          {formatElapsed(now - startedAt)}
        </span>
      </div>
      <ol aria-live="polite" className="flex flex-col">
        {steps.map((step, index) => (
          <li
            key={step.number}
            className="flex animate-in gap-3.5 border-b border-line-subtle py-3 duration-200 fade-in"
          >
            {index === running ? (
              <span
                aria-hidden="true"
                className="size-6 shrink-0 animate-spin rounded-full border-[2.5px] border-line-mid border-t-brand"
              />
            ) : (
              <span
                aria-hidden="true"
                className="flex size-6 shrink-0 items-center justify-center rounded-full bg-verified-bg-2"
              >
                <Check className="size-3.5 text-verified-strong" strokeWidth={3} />
              </span>
            )}
            <span className="font-semibold">{step.label}</span>
          </li>
        ))}
      </ol>
      {steps.length === 0 && (
        <p className="py-3 text-sm text-muted-foreground">Waiting for the first step.</p>
      )}
      <Button
        variant="outline"
        onClick={onStop}
        className="mt-4.5 min-h-target w-full text-[15px] text-foreground-2 dark:bg-transparent"
      >
        Stop
      </Button>
    </section>
  );
}
