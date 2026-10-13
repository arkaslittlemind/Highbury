"use client";

import { useId, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";

// The limit of the service (MAX_QUESTION_LENGTH in api.py).
export const MAX_QUESTION_LENGTH = 500;

type QuestionBarProps = {
  label: string;
  placeholder: string;
  onAsk: (question: string) => void;
};

/** The bar for a follow-up, below an answer. The landing screen has AskPill. */
export function QuestionBar({ label, placeholder, onAsk }: QuestionBarProps) {
  const inputId = useId();
  const [question, setQuestion] = useState("");
  const trimmed = question.trim();

  function submit(event: FormEvent) {
    event.preventDefault();
    if (trimmed) onAsk(trimmed);
  }

  return (
    <form
      onSubmit={submit}
      // On a phone the bar stays at the bottom of the screen.
      className="flex flex-col gap-3.5 rounded-panel border border-line-mid bg-card p-5 max-sm:sticky max-sm:bottom-0 max-sm:z-20 max-sm:-mx-4 max-sm:rounded-none max-sm:border-x-0 max-sm:border-b-0 max-sm:bg-background max-sm:px-4 max-sm:py-3"
    >
      <label
        htmlFor={inputId}
        // The label stays as the name of the input when it is not in view.
        className="font-display text-base font-bold tracking-[0.14em] text-foreground-2 uppercase max-sm:sr-only"
      >
        {label}
      </label>
      <div className="flex gap-3 max-sm:gap-2 sm:flex-wrap">
        <input
          id={inputId}
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={placeholder}
          maxLength={MAX_QUESTION_LENGTH}
          autoComplete="off"
          className="h-12 min-w-0 flex-1 rounded-lg border border-input bg-background px-3.5 text-base placeholder:text-faint sm:h-14 sm:flex-[1_1_420px] sm:px-4.5 sm:text-lg"
        />
        <Button
          type="submit"
          disabled={!trimmed}
          className="h-12 px-5 font-display text-lg font-bold tracking-[0.1em] uppercase sm:h-14 sm:px-7 sm:text-xl"
        >
          Ask
        </Button>
      </div>
    </form>
  );
}
