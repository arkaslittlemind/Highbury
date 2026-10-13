import { TriangleAlert } from "lucide-react";

import { AskPage } from "@/components/ask/ask-page";
import { SiteHeader } from "@/components/ask/site-header";
import { StateCard } from "@/components/ask/state-card";

export default function Home() {
  // Next.js puts the value into the bundle at build time. A change needs a new build.
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  return (
    <>
      {apiUrl ? (
        <AskPage apiUrl={apiUrl} />
      ) : (
        <>
          <SiteHeader />
          <main className="mx-auto flex w-full max-w-[1360px] flex-1 flex-col gap-8 px-4 pt-12 pb-16 sm:px-10">
            <StateCard
              tone="error"
              icon={TriangleAlert}
              tag="Not set up"
              title="This page cannot reach the analyst API."
              alert
            >
              <p className="text-foreground-2">NEXT_PUBLIC_API_URL is not set.</p>
            </StateCard>
          </main>
        </>
      )}
      <footer className="flex flex-wrap justify-between gap-x-6 gap-y-2 border-t px-4 py-6 text-sm text-muted-foreground sm:px-10">
        <span>
          Unofficial fan project. Not affiliated with or endorsed by Arsenal FC or the Premier
          League.
        </span>
        <span>Data: StatsBomb Open Data · Understat</span>
      </footer>
    </>
  );
}
