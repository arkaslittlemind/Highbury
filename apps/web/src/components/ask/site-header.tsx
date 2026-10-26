import { PillDisc, pill } from "@/components/ask/pill";
import { cn } from "@/lib/utils";

// The sections of the landing screen. Each one has the id of its link.
const SECTIONS = [
  { href: "#how", label: "How it works" },
  { href: "#seasons", label: "Seasons" },
  { href: "#sample", label: "Sample answer" },
];

type SiteHeaderProps = {
  onNewQuestion?: () => void;
  // The landing screen gives this. The header then lies on the hero, with the
  // links to the sections, and its button sends the visitor to the question bar.
  onAsk?: () => void;
};

export function SiteHeader({ onNewQuestion, onAsk }: SiteHeaderProps) {
  return (
    <header
      // The header has the width of the content below it: the hero is narrower
      // than the other screens.
      className={cn(
        "mx-auto w-full px-4 pt-3 sm:px-10 sm:pt-8",
        onAsk ? "absolute inset-x-0 top-0 z-10 max-w-[1280px]" : "max-w-[1360px]",
      )}
    >
      <div className="flex min-h-15 items-center justify-between gap-4 rounded-full border border-white/18 bg-white/8 py-1.5 pr-1.5 pl-5 backdrop-blur-lg sm:min-h-18.5 sm:py-3 sm:pr-3 sm:pl-7">
        <div className="flex items-center gap-2.5">
          {/* A plain football. The page has no crest and no logo of a club. */}
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="size-6.5 fill-none stroke-foreground"
            strokeWidth={1.6}
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="9.5" />
            <path d="M12 7.2l3.6 2.6-1.4 4.2H9.8L8.4 9.8z" />
            <path d="M12 7.2V2.6M15.6 9.8l4.3-1.5M14.2 14l2.7 3.7M9.8 14l-2.7 3.7M8.4 9.8L4.1 8.3" />
          </svg>
          <span className="font-display text-[26px] leading-none font-extrabold tracking-[0.06em] uppercase">
            Highbury
          </span>
        </div>
        {onAsk && (
          <nav aria-label="Primary" className="flex gap-8 max-lg:hidden">
            {SECTIONS.map(({ href, label }) => (
              <a
                key={href}
                href={href}
                className="flex min-h-target items-center text-on-grass transition-colors duration-150 hover:text-white"
              >
                {label}
              </a>
            ))}
          </nav>
        )}
        {onAsk && (
          <button type="button" onClick={onAsk} className={pill}>
            {/* A phone has room for the first word only. */}
            <span>
              Ask<span className="max-sm:sr-only"> the Analyst</span>
            </span>
            <PillDisc />
          </button>
        )}
        {onNewQuestion && (
          <button
            type="button"
            onClick={onNewQuestion}
            className={cn(pill, "max-sm:size-12 max-sm:justify-center max-sm:gap-0 max-sm:p-0")}
          >
            {/* A phone shows the icon only, on one paper disc. The text stays as the name of the button. */}
            <span className="max-sm:sr-only">New question</span>
            <PillDisc icon="plus" className="max-sm:bg-transparent max-sm:text-background" />
          </button>
        )}
      </div>
    </header>
  );
}
