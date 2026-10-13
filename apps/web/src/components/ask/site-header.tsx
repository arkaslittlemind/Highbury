import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";

type SiteHeaderProps = {
  onNewQuestion?: () => void;
  // The link to the strip, for a screen that has the strip.
  howLink?: boolean;
};

export function SiteHeader({ onNewQuestion, howLink = false }: SiteHeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b px-4 py-3 sm:px-10 sm:py-4.5">
      <div className="flex items-baseline gap-3">
        <span className="font-display text-[28px] font-extrabold tracking-[0.06em] uppercase">
          Highbury
        </span>
        <span className="text-sm text-muted-foreground max-sm:hidden">AI football analyst</span>
      </div>
      {howLink && (
        <nav aria-label="Primary">
          <a
            href="#how"
            className="flex min-h-target items-center text-[15px] text-foreground-2 hover:text-foreground"
          >
            How it works
          </a>
        </nav>
      )}
      {onNewQuestion && (
        <Button
          variant="outline"
          onClick={onNewQuestion}
          className="min-h-target px-4 text-[15px] max-sm:w-11 max-sm:px-0 dark:bg-transparent"
        >
          {/* A phone shows the icon only. The text stays as the name of the button. */}
          <Plus aria-hidden="true" className="size-5 sm:hidden" />
          <span className="max-sm:sr-only">New question</span>
        </Button>
      )}
    </header>
  );
}
