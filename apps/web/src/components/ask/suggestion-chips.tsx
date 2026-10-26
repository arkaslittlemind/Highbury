import { cn } from "@/lib/utils";

type SuggestionChipsProps = {
  questions: string[];
  onPick: (question: string) => void;
  // A short label before the chips, such as "Try asking".
  lead?: string;
  // The chips arrive one by one. For chips that come after the page is in view.
  stagger?: boolean;
};

export function SuggestionChips({ questions, onPick, lead, stagger = false }: SuggestionChipsProps) {
  if (questions.length === 0 && !lead) return null;
  return (
    <div className="flex flex-wrap items-center gap-2.5">
      {lead && (
        <span className="mr-1.5 font-display text-sm font-semibold tracking-[0.18em] text-muted-foreground uppercase">
          {lead}
        </span>
      )}
      {questions.map((question, index) => (
        <button
          key={question}
          type="button"
          onClick={() => onPick(question)}
          // The step comes from the place of the chip in the row, so it cannot be a class.
          style={stagger ? { animationDelay: `${index * 60}ms` } : undefined}
          className={cn(
            "min-h-target cursor-pointer rounded-full border border-line-strong px-4 py-2 text-left text-[15px] transition-[scale,border-color,background-color] duration-150 ease-out hover:border-foreground-2 hover:bg-white/5 active:scale-[0.97]",
            stagger &&
              "animate-in fill-mode-both duration-300 ease-out-strong fade-in slide-in-from-bottom-2",
          )}
        >
          {question}
        </button>
      ))}
    </div>
  );
}
