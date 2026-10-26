export function AnswerSkeleton() {
  return (
    <section
      aria-label="Answer loading"
      className="flex min-w-0 flex-[999_1_560px] flex-col gap-4.5"
    >
      <div className="h-4.5 w-[86%] animate-pulse rounded-sm bg-skeleton" />
      <div className="h-4.5 w-[64%] animate-pulse rounded-sm bg-skeleton" />
      <div className="h-[420px] animate-pulse rounded-panel border bg-surface-chart" />
    </section>
  );
}
