import { cn } from "@/lib/utils";

type TryLinkProps = {
  label: string;
  question: string;
  // Puts the question into the hero bar. It does not ask it.
  onTry: (question: string) => void;
  className?: string;
};

/** "Try: …", the link of a card that fills the hero bar with its question. */
export function TryLink({ label, question, onTry, className }: TryLinkProps) {
  return (
    <button
      type="button"
      onClick={() => onTry(question)}
      className={cn(
        "group inline-flex min-h-target cursor-pointer items-center gap-2 self-end justify-self-start px-0.5 text-left text-[15px] font-semibold underline decoration-line-strong underline-offset-[5px] transition-[text-decoration-color,scale] duration-150 ease-out-strong hover:decoration-foreground active:scale-[0.97]",
        className,
      )}
    >
      <span>
        Try: {label}
        <span
          aria-hidden="true"
          className="ml-2 inline-block transition-transform duration-200 ease-out-strong group-hover:translate-x-[3px]"
        >
          →
        </span>
      </span>
    </button>
  );
}
