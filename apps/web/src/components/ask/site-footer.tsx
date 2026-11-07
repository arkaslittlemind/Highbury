import Image from "next/image";
import { Suspense } from "react";

import logo from "@/app/icon.svg";
import stadium from "@/assets/footer-stadium.webp";
import { ApiStatus } from "@/components/ask/api-status";
import styles from "@/components/ask/site-footer.module.css";
import { VisitCount } from "@/components/ask/visit-count";
import { NOTICE } from "@/lib/landing-content";

type FooterLink = { href: string; label: string };

// The Product links name the ids of the landing sections. On the answer screen
// those sections are not in the page, so the links do nothing there.
const COLUMNS: { title: string; links: FooterLink[] }[] = [
  {
    title: "Product",
    links: [
      { href: "#how", label: "How it works" },
      { href: "#faq-title", label: "FAQ" },
      { href: "#hero-title", label: "Ask a question" },
    ],
  },
  {
    title: "Data",
    links: [
      { href: "https://github.com/statsbomb/open-data", label: "StatsBomb Open Data" },
      { href: "https://understat.com/", label: "Understat" },
      { href: "https://www.football-data.co.uk/", label: "football-data.co.uk" },
      { href: "https://github.com/vaastav/Fantasy-Premier-League", label: "FPL archive" },
    ],
  },
  {
    title: "For AI agents",
    links: [
      { href: "/llms.txt", label: "llms.txt" },
      { href: "/llms-full.txt", label: "llms-full.txt" },
      { href: "/index.md", label: "index.md" },
    ],
  },
];

const REPO_URL = "https://github.com/arkaslittlemind/Highbury";

export function SiteFooter({ apiUrl }: { apiUrl: string | undefined }) {
  return (
    <footer className="mx-auto w-full max-w-[1240px] px-gutter max-[600px]:px-2">
      <div className="relative isolate overflow-hidden rounded-t-3xl border border-b-0 border-border bg-card">
        <div className="px-14 pt-16 pb-8 max-[960px]:px-8 max-[960px]:pt-12 max-[960px]:pb-7 max-[600px]:px-5 max-[600px]:pt-10 max-[600px]:pb-6">
          <div className="grid grid-cols-[minmax(0,1.5fr)_repeat(3,minmax(0,1fr))] gap-10 max-[960px]:grid-cols-3 max-[600px]:grid-cols-2 max-[600px]:gap-x-5 max-[600px]:gap-y-8">
            <div className="grid content-start gap-5 max-[960px]:col-span-full">
              <a href="#" className="flex items-center gap-3 self-start">
                {/* The football of the site icon, not the crest of a club. */}
                <Image src={logo} alt="" width={32} height={32} unoptimized className="rounded-lg" />
                <span className="font-display text-[22px] leading-none font-extrabold tracking-[0.06em] uppercase">
                  Highbury
                </span>
              </a>
              <p className="max-w-[34ch] text-base leading-[1.6] text-foreground-2">
                An AI football analyst for two Arsenal eras. Ask in plain English; every number is
                checked before you see it.
              </p>
              <div className="flex gap-1.5">
                <a
                  href={REPO_URL}
                  aria-label="Highbury on GitHub"
                  className="grid size-10 place-items-center rounded-[10px] text-muted-foreground transition-colors duration-150 hover:bg-line-subtle hover:text-foreground"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.9 1.52 2.34 1.08 2.91.83.09-.65.35-1.08.63-1.33-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.65 0 0 .84-.27 2.75 1.02a9.56 9.56 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02.55 1.38.2 2.4.1 2.65.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 12 2z" />
                  </svg>
                </a>
              </div>
              <ApiStatus apiUrl={apiUrl} />
            </div>
            {COLUMNS.map((column) => (
              <nav key={column.title} aria-label={column.title}>
                <h3 className="mt-1.5 mb-4.5 font-mono text-xs leading-none font-medium tracking-[0.14em] text-muted-foreground uppercase">
                  {column.title}
                </h3>
                <ul className="grid gap-1">
                  {column.links.map((link) => (
                    <li key={link.href}>
                      <a
                        href={link.href}
                        className="inline-flex min-h-9 items-center text-[15.5px] text-foreground-2 transition-colors duration-150 hover:text-foreground"
                      >
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
          <div className="mt-14 flex flex-wrap items-center justify-between gap-4 border-t border-line-subtle pt-6 text-sm text-muted-foreground max-[600px]:mt-10 max-[600px]:flex-col max-[600px]:items-start">
            <p>© 2026 Highbury · {NOTICE}</p>
            {/* The count is cached on the server, so the fallback shows only while a new entry fills. */}
            <Suspense fallback={null}>
              <VisitCount />
            </Suspense>
          </div>
        </div>
        <div aria-hidden="true" className={styles.art}>
          <Image src={stadium} alt="" fill sizes="(max-width: 1240px) 100vw, 1240px" />
        </div>
      </div>
    </footer>
  );
}
