const LINE = { strokeWidth: 0.4 } as const;

// Decoration only: these marks are not shots of the data.
const THEN_MARKS = [
  { cx: 14, cy: 34, r: 2.6, goal: true },
  { cx: 10, cy: 42, r: 3.4, goal: true },
  { cx: 19, cy: 47, r: 1.8, goal: false },
  { cx: 24, cy: 31, r: 1.5, goal: false },
  { cx: 8, cy: 37, r: 2.2, goal: true },
  { cx: 27, cy: 52, r: 1.3, goal: false },
];
const NOW_MARKS = [
  { cx: 106, cy: 38, r: 2.8, goal: true },
  { cx: 111, cy: 44, r: 3.2, goal: true },
  { cx: 101, cy: 49, r: 1.7, goal: false },
  { cx: 96, cy: 33, r: 1.4, goal: false },
  { cx: 113, cy: 35, r: 2.1, goal: true },
  { cx: 93, cy: 47, r: 1.2, goal: false },
];

/** One pitch with a season in each half. It is a picture of the idea and holds no data. */
function EraPitch() {
  return (
    <figure
      aria-hidden="true"
      className="min-w-0 flex-[1_1_460px] rounded-lg border bg-surface-chart p-5"
    >
      <div className="flex justify-between gap-3 px-1 pb-3 font-display text-[13px] font-bold tracking-[0.08em] uppercase sm:text-[15px] sm:tracking-[0.14em]">
        <span>2003-04 · StatsBomb</span>
        <span className="text-right text-brand">Understat · 2025-26</span>
      </div>
      <svg viewBox="-2 -2 124 84" className="block w-full fill-none stroke-line-strong">
        <rect x="0" y="0" width="120" height="80" className="fill-pitch" {...LINE} />
        <rect x="0" y="0" width="60" height="80" className="fill-pitch-alt stroke-none" />
        <line x1="60" y1="0" x2="60" y2="80" {...LINE} />
        <circle cx="60" cy="40" r="10" {...LINE} />
        <rect x="0" y="18" width="18" height="44" {...LINE} />
        <rect x="0" y="30" width="6" height="20" {...LINE} />
        <rect x="102" y="18" width="18" height="44" {...LINE} />
        <rect x="114" y="30" width="6" height="20" {...LINE} />
        {THEN_MARKS.map(({ goal, ...circle }) => (
          <circle
            key={circle.cx}
            {...circle}
            {...LINE}
            className={goal ? "fill-foreground stroke-none" : "stroke-foreground"}
          />
        ))}
        {NOW_MARKS.map(({ goal, ...circle }) => (
          <circle
            key={circle.cx}
            {...circle}
            {...LINE}
            className={goal ? "fill-brand stroke-none" : "stroke-brand"}
          />
        ))}
      </svg>
      <div className="flex justify-between gap-3 px-1 pt-3 text-[13px] text-muted-foreground">
        <span>26 W · 12 D · 0 L</span>
        <span className="text-right">Shots · xG · player stats</span>
      </div>
    </figure>
  );
}

/** The top of the first screen: what Highbury is, before a visitor asks. */
export function Hero() {
  return (
    <section
      aria-labelledby="hero-title"
      className="flex flex-wrap items-center gap-x-14 gap-y-8 sm:py-6"
    >
      <div className="flex min-w-0 flex-[1_1_520px] flex-col gap-4 sm:gap-5.5">
        <div className="flex items-center gap-2.5 font-display text-[15px] font-semibold tracking-[0.16em] text-foreground-2 uppercase">
          <span aria-hidden="true" className="h-[3px] w-7 bg-brand-strong" />
          Two seasons. One analyst.
        </div>
        <h1
          id="hero-title"
          className="font-display text-[54px] leading-[0.9] font-extrabold tracking-[-0.01em] uppercase sm:text-[72px] lg:text-[104px]"
        >
          The Invincibles
          <br />
          <span className="text-brand">
            <span aria-hidden="true">↔</span>
            <span className="sr-only">and</span> 2025-26
          </span>
        </h1>
        <p className="max-w-[540px] text-lg text-foreground-2 sm:text-xl">
          Ask in plain English. Every number is checked against the data before you see it,
          and when the data cannot answer, Highbury says so.
        </p>
      </div>
      <EraPitch />
    </section>
  );
}
