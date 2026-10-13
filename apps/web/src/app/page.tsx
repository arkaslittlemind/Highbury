import { ConnectionCheck } from "@/components/connection-check";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Highbury</h1>
        <p className="text-muted-foreground">
          An AI football analyst for Arsenal&apos;s 2003-04 and 2025-26 seasons.
          The full page is not built yet. This page checks the connection to
          the analyst.
        </p>
      </header>
      <ConnectionCheck />
      <footer className="text-sm text-muted-foreground">
        Unofficial fan project. Not affiliated with or endorsed by Arsenal FC or
        the Premier League.
      </footer>
    </main>
  );
}
