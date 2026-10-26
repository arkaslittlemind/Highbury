import { AskPill } from "@/components/ask/ask-pill";

type QuestionBarProps = {
  label: string;
  placeholder: string;
  onAsk: (question: string) => void;
};

/** The bar for a follow-up, below an answer: the pill of the landing screen on a dark card. */
export function QuestionBar({ label, placeholder, onAsk }: QuestionBarProps) {
  return (
    <div
      // On a phone the bar stays at the bottom of the screen.
      className="flex flex-col gap-3.5 rounded-panel border border-line-mid bg-card p-5 max-sm:sticky max-sm:bottom-0 max-sm:z-20 max-sm:-mx-4 max-sm:rounded-none max-sm:border-x-0 max-sm:border-b-0 max-sm:bg-background max-sm:px-4 max-sm:py-3"
    >
      {/* The input has the same text as its label, so this copy is only for the eye. */}
      <span
        aria-hidden="true"
        className="font-display text-base font-bold tracking-[0.14em] text-foreground-2 uppercase max-sm:hidden"
      >
        {label}
      </span>
      <AskPill
        label={label}
        placeholder={placeholder}
        onAsk={onAsk}
        className="border-line-strong bg-background focus-within:border-foreground-2 focus-within:bg-background"
      />
    </div>
  );
}
