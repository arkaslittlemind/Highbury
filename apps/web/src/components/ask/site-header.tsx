import Image from "next/image";

import logo from "@/app/icon.svg";
import { pill } from "@/components/ask/pill";
import { cn } from "@/lib/utils";

// The sections of the landing screen. Each one has the id of its link.
const SECTIONS = [
  { href: "#how", label: "How it works" },
  { href: "#seasons", label: "Seasons" },
  { href: "#faq", label: "FAQ" },
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
        "mx-auto w-full",
        onAsk
          ? "absolute inset-x-0 top-0 z-10 max-w-[1200px] px-gutter pt-5"
          : "max-w-[1360px] px-4 pt-3 sm:px-10 sm:pt-8",
      )}
    >
      <div
        className={cn(
          "flex min-h-15 items-center justify-between gap-4 rounded-full border border-white/14 bg-[rgb(10_18_14/0.4)] py-1.5 pr-2 pl-5 backdrop-blur-md",
          // A phone has no button on the landing screen, so the name is not off centre.
          onAsk && "max-[600px]:pr-5",
        )}
      >
        {/* The name and the button take equal sides, so the links sit on the
            centre line of the page, whatever the widths of the two. */}
        <div className="flex flex-1 items-center gap-3">
          {/* The football of the site icon. The site uses no crest or club logo as its branding. */}
          <Image src={logo} alt="" width={32} height={32} unoptimized className="rounded-lg" />
          <span className="font-display text-xl leading-none font-extrabold tracking-[0.06em] uppercase">
            Highbury
          </span>
        </div>
        {onAsk && (
          // Equal outer columns put the middle link, not the block, on the centre line:
          // "How it works" is much wider than "FAQ".
          <nav
            aria-label="Primary"
            className="grid grid-cols-[1fr_auto_1fr] gap-7 text-[15px] max-[960px]:hidden"
          >
            {SECTIONS.map(({ href, label }) => (
              <a
                key={href}
                href={href}
                className="flex min-h-target items-center text-on-grass transition-colors duration-150 first:justify-self-end last:justify-self-start hover:text-white"
              >
                {label}
              </a>
            ))}
          </nav>
        )}
        {onAsk && (
          <div className="flex flex-1 justify-end max-[600px]:hidden">
            <button type="button" onClick={onAsk} className={cn(pill, "min-h-11 text-[15px]")}>
              Ask the Analyst
            </button>
          </div>
        )}
        {onNewQuestion && (
          <button type="button" onClick={onNewQuestion} className={pill}>
            {/* A phone has room for the first word only. */}
            <span>
              New<span className="max-sm:sr-only"> question</span>
            </span>
          </button>
        )}
      </div>
    </header>
  );
}
