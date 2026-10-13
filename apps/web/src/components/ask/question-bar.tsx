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
        large
          ? "gap-4 p-5 sm:p-7"
          : // On a phone the follow-up bar stays at the bottom of the screen.
            "gap-3.5 p-5 max-sm:sticky max-sm:bottom-0 max-sm:z-20 max-sm:-mx-4 max-sm:rounded-none max-sm:border-x-0 max-sm:border-b-0 max-sm:bg-background max-sm:px-4 max-sm:py-3",
      )}
    >
      <label
        htmlFor={inputId}
        className={cn(
          "font-display font-bold tracking-[0.14em] text-foreground-2 uppercase",
          // The label stays as the name of the input when it is not in view.
          large ? "text-lg" : "text-base max-sm:sr-only",
        )}
      >
        {label}
      </label>
      <div className={cn("flex gap-3", large ? "flex-wrap" : "max-sm:gap-2 sm:flex-wrap")}>
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
            large
              ? "h-14 flex-[1_1_480px] px-4.5 text-lg sm:h-16 sm:px-5.5 sm:text-xl"
              : "h-12 flex-1 px-3.5 text-base sm:h-14 sm:flex-[1_1_420px] sm:px-4.5 sm:text-lg",
          )}
        />
        <Button
          type="submit"
          disabled={!trimmed}
          className={cn(
            "font-display font-bold tracking-[0.1em] uppercase",
            large
              ? "h-14 px-7 text-xl sm:h-16 sm:px-8 sm:text-[22px]"
              : "h-12 px-5 text-lg sm:h-14 sm:px-7 sm:text-xl",
          )}
        >
          Ask
        </Button>
      </div>
      {children}
    </form>
  );
}
