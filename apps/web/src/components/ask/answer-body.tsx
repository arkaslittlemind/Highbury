import { Ban, CircleMinus } from "lucide-react";

import { StateCard } from "@/components/ask/state-card";
import { SuggestionChips } from "@/components/ask/suggestion-chips";
import { Button } from "@/components/ui/button";
import type { Answer } from "@/lib/analyst-schema";

type AnswerBodyProps = {
  answer: Answer;
  suggestions: string[];
  // Ask the alternative of an answer, in the same conversation.
  onAskAlternative: (question: string) => void;
  // Ask a suggestion. It starts a conversation, so the service can give its kept answer.
  onAskSuggestion: (question: string) => void;
};

/** What the analyst said: the summary, or the card of a question that the data cannot answer. */
export function AnswerBody({
  answer,
  suggestions,
  onAskAlternative,
  onAskSuggestion,
}: AnswerBodyProps) {
  if (answer.status === "answered") {
    return <p className="text-[21px] leading-normal">{answer.summary}</p>;
  }

  if (answer.status === "unavailable") {
    const { alternative } = answer;
    return (
      <StateCard tone="caveat" icon={CircleMinus} tag="Data not available">
        <p className="text-lg text-foreground-2">{answer.summary}</p>
        {alternative && (
          <div className="flex flex-col gap-3 rounded-lg border bg-background p-4">
            <span className="text-sm text-muted-foreground">What I can show instead</span>
            <div>
              <Button
                onClick={() => onAskAlternative(alternative)}
                className="h-auto min-h-target px-4.5 py-2 text-left text-base font-semibold whitespace-normal"
              >
                {alternative}
              </Button>
            </div>
          </div>
        )}
      </StateCard>
    );
  }

  return (
    <StateCard tone="neutral" icon={Ban} tag="Out of scope">
      <p className="text-lg text-foreground-2">{answer.summary}</p>
      {suggestions.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <span className="text-sm text-muted-foreground">Questions it can answer</span>
          <SuggestionChips questions={suggestions} onPick={onAskSuggestion} />
        </div>
      )}
    </StateCard>
  );
}
