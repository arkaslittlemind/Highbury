"use client";

import { useId, useRef, useState, type FormEvent, type RefObject } from "react";

import { PillDisc, pill } from "@/components/ask/pill";
import { cn } from "@/lib/utils";

// The limit of the service (MAX_QUESTION_LENGTH in api.py).
export const MAX_QUESTION_LENGTH = 500;

type AskPillProps = {
  label: string;
  placeholder: string;
  onAsk: (question: string) => void;
  // The text that the bar starts with. With a text, the bar takes the focus.
  initialQuestion?: string;
  // For a control in a different place that sends the visitor to this bar.
  inputRef?: RefObject<HTMLInputElement | null>;
  className?: string;
};

/** The question bar: one row of glass on the grass, or on a card below an answer. */
export function AskPill({
  label,
  placeholder,
  onAsk,
  initialQuestion = "",
  inputRef,
  className,
}: AskPillProps) {
  const inputId = useId();
  const ownRef = useRef<HTMLInputElement>(null);
  const input = inputRef ?? ownRef;
  const [question, setQuestion] = useState(initialQuestion);

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    // The button is not disabled, so that the first action of the page looks
    // ready. With no text, it sends the visitor to the input.
    if (trimmed) onAsk(trimmed);
    else input.current?.focus();
  }

  return (
    <form
      onSubmit={submit}
      // The ring of the focus goes around the row and not around the input in it.
      className={cn(
        "flex items-center gap-1.5 rounded-full border border-white/20 bg-background/45 p-1.5 backdrop-blur-md transition-[border-color,background-color] duration-200 ease-out focus-within:border-white/45 focus-within:bg-background/60 has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-3 has-[input:focus-visible]:outline-ring",
        className,
      )}
    >
      <label htmlFor={inputId} className="sr-only">
        {label}
      </label>
      <input
        ref={input}
        id={inputId}
        type="text"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        placeholder={placeholder}
        maxLength={MAX_QUESTION_LENGTH}
        autoComplete="off"
        // A phone shows "Go" on the key that sends the form.
        enterKeyHint="go"
        autoFocus={initialQuestion !== ""}
        // 16px or more, so that iOS does not zoom the page on focus.
        className="h-12 min-w-0 flex-1 bg-transparent pr-2 pl-4 text-base text-ellipsis outline-hidden placeholder:text-on-grass-muted/75 sm:pl-5 sm:text-lg"
      />
      <button type="submit" className={cn(pill, "text-[17px]")}>
        Ask
        <PillDisc />
      </button>
    </form>
  );
}
