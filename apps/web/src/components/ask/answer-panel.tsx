"use client";

import { useRef, type Ref, type RefObject } from "react";

import { AnswerBody } from "@/components/ask/answer-body";
import { AnswerMeta } from "@/components/ask/answer-meta";
import { CaveatNote } from "@/components/ask/caveat-note";
import { ChartPanel } from "@/components/ask/chart-panel";
import { QuestionHeading } from "@/components/ask/question-heading";
import { VerificationList } from "@/components/ask/verification-list";
import { WorkingList } from "@/components/ask/working-list";
import type { AnswerData } from "@/lib/analyst-schema";
import { badgeState, chartsOfAnswer, formatElapsed, type Turn } from "@/lib/ask-state";

type AnswerPanelProps = {
  turn: Turn;
  data: AnswerData;
  // The time of performance.now() when the answer came.
  endedAt: number;
  titleRef: Ref<HTMLHeadingElement>;
  suggestions: string[];
  onAsk: (question: string, options?: { asNew?: boolean }) => void;
};

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

function reveal(details: RefObject<HTMLDetailsElement | null>) {
  if (!details.current) return;
  details.current.open = true;
  details.current.scrollIntoView({ block: "nearest" });
}

function revealRow(details: RefObject<HTMLDetailsElement | null>, row: number) {
  if (!details.current) return;
  details.current.open = true;
  const item = details.current.querySelector<HTMLElement>(`[data-row="${row}"]`);
  item?.scrollIntoView({ block: "center" });
  item?.focus({ preventScroll: true });
}

export function AnswerPanel({ turn, data, endedAt, titleRef, suggestions, onAsk }: AnswerPanelProps) {
  const verificationRef = useRef<HTMLDetailsElement>(null);
  const workingRef = useRef<HTMLDetailsElement>(null);

  const { answer, verification, working } = data;
  const badge = badgeState(verification);
  const charts = chartsOfAnswer(answer.charts, turn.charts);
  const elapsed = formatElapsed(endedAt - turn.startedAt);
  const stepCount = turn.steps.length;
  const timing =
    stepCount > 0 ? `Answered in ${elapsed} · ${plural(stepCount, "step", "steps")}` : `Answered in ${elapsed}`;
  const unbacked = verification.unbacked_numbers;

  return (
    <>
      <QuestionHeading turn={turn} titleRef={titleRef}>
        <AnswerMeta
          badge={badge}
          verification={verification}
          timing={timing}
          onOpenVerification={() => reveal(verificationRef)}
          onOpenWorking={working.length > 0 ? () => reveal(workingRef) : undefined}
        />
      </QuestionHeading>

      <div className="flex flex-wrap items-start gap-8">
        <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-6">
          <AnswerBody
            answer={answer}
            suggestions={suggestions}
            onAskAlternative={(question) => onAsk(question)}
            onAskSuggestion={(question) => onAsk(question, { asNew: true })}
          />
          {badge !== "none" && (
            <VerificationList
              claims={answer.claims}
              verification={verification}
              partial={badge === "partial"}
              working={working}
              onShowCall={(row) => revealRow(workingRef, row)}
              detailsRef={verificationRef}
            />
          )}
          {unbacked.length > 0 && (
            <CaveatNote
              title="Numbers with no checked claim"
              text={`The summary gives ${unbacked.join(", ")}, and no checked claim backs ${unbacked.length === 1 ? "it" : "them"}.`}
            />
          )}
          {answer.caveats.map((caveat, index) => (
            <CaveatNote key={index} title="Caveat" text={caveat} />
          ))}
        </div>
        {charts.length > 0 && (
          <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-6">
            {charts.map(({ id, chart }) => (
              <ChartPanel key={id} chart={chart} />
            ))}
          </div>
        )}
      </div>

      {working.length > 0 && (
        <WorkingList
          working={working}
          totals={`${plural(working.length, "tool call", "tool calls")} · ${elapsed}`}
          detailsRef={workingRef}
        />
      )}
    </>
  );
}
