"use client";

import { useId, useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// The limit of the service (MAX_QUESTION_LENGTH in api.py).
const MAX_QUESTION_LENGTH = 500;

type QuestionBarProps = {
  label: string;
  placeholder: string;
  onAsk: (question: string) => void;
  // The text that the bar starts with. With a text, the bar takes the focus.
  initialQuestion?: string;
  // The first bar of the page is larger than the follow-up bar.
  large?: boolean;
  // Chips and notes under the bar.
  children?: ReactNode;
};

export function QuestionBar({
  label,
  placeholder,
  onAsk,
  initialQuestion = "",
  large = false,
  children,
}: QuestionBarProps) {
  const inputId = useId();
  const [question, setQuestion] = useState(initialQuestion);
  const trimmed = question.trim();

  function submit(event: FormEvent) {
    event.preventDefault();
    if (trimmed) onAsk(trimmed);
  }

  return (
    <form
      onSubmit={submit}
      className={cn(
        "flex flex-col rounded-panel border border-line-mid bg-card",
        large ? "gap-4 p-7" : "gap-3.5 p-5",
      )}
    >
      <label
        htmlFor={inputId}
        className={cn(
          "font-display font-bold tracking-[0.14em] text-foreground-2 uppercase",
          large ? "text-lg" : "text-base",
        )}
      >
        {label}
      </label>
      <div className="flex flex-wrap gap-3">
        <input
          id={inputId}
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={placeholder}
          maxLength={MAX_QUESTION_LENGTH}
          autoComplete="off"
          autoFocus={initialQuestion !== ""}
          className={cn(
            "min-w-0 rounded-lg border border-input bg-background placeholder:text-faint",
            large ? "h-16 flex-[1_1_480px] px-5.5 text-xl" : "h-14 flex-[1_1_420px] px-4.5 text-lg",
          )}
        />
        <Button
          type="submit"
          disabled={!trimmed}
          className={cn(
            "font-display font-bold tracking-[0.1em] uppercase",
            large ? "h-16 px-8 text-[22px]" : "h-14 px-7 text-xl",
          )}
        >
          Ask
        </Button>
      </div>
      {children}
    </form>
  );
}
