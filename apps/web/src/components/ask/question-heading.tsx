import type { ReactNode, Ref } from "react";

import type { Turn } from "@/lib/ask-state";

type QuestionHeadingProps = {
  turn: Turn;
  // The page moves the focus here when an answer or a state arrives.
  titleRef: Ref<HTMLHeadingElement>;
  // The line under the title.
  children?: ReactNode;
};

export function QuestionHeading({ turn, titleRef, children }: QuestionHeadingProps) {
  return (
    <div className="flex flex-col gap-3.5">
      <span className="font-display text-[15px] font-semibold tracking-[0.16em] text-muted-foreground uppercase">
        {turn.followUp ? "Follow-up" : "Your question"}
      </span>
      <h1
        ref={titleRef}
        tabIndex={-1}
        className="max-w-[960px] font-display text-4xl leading-[1.05] font-bold wrap-break-word sm:text-5xl"
      >
        {turn.question}
      </h1>
      {children}
    </div>
  );
}
