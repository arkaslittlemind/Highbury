import { Button } from "@/components/ui/button";

export function SiteHeader({ onNewQuestion }: { onNewQuestion?: () => void }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b px-4 py-4.5 sm:px-10">
      <div className="flex items-baseline gap-3">
        <span className="font-display text-[28px] font-extrabold tracking-[0.06em] uppercase">
          Highbury
        </span>
        <span className="text-sm text-muted-foreground">AI football analyst</span>
      </div>
      {onNewQuestion && (
        <Button
          variant="outline"
          onClick={onNewQuestion}
          className="min-h-target px-4 text-[15px] dark:bg-transparent"
        >
          New question
        </Button>
      )}
    </header>
  );
}
