type SuggestionChipsProps = {
  questions: string[];
  onPick: (question: string) => void;
  // A short word before the chips, such as "Try".
  lead?: string;
};

export function SuggestionChips({ questions, onPick, lead }: SuggestionChipsProps) {
  if (questions.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2.5">
      {lead && <span className="mr-1 text-sm text-muted-foreground">{lead}</span>}
      {questions.map((question) => (
        <button
          key={question}
          type="button"
          onClick={() => onPick(question)}
          className="min-h-target cursor-pointer rounded-full border border-line-strong px-4 py-2 text-left text-[15px] hover:border-foreground-2"
        >
          {question}
        </button>
      ))}
    </div>
  );
}
