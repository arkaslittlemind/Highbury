import { Database, Lock, ShieldCheck, type LucideIcon } from "lucide-react";

const CARDS: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: Database,
    title: "Data catalog first",
    text: "The agent reads what each season holds before it writes a query, so it knows that 2025-26 has shots but no passes.",
  },
  {
    icon: Lock,
    title: "Read-only SQL",
    text: "One SELECT in each call, checked by a parser and run as a read-only role with a 5-second timeout and a row limit.",
  },
  {
    icon: ShieldCheck,
    title: "Claim verifier",
    text: "Plain code checks every number against the tool output that it cites. A claim with no support is removed before you see it.",
  },
];

/** The three things that make an answer one that a visitor can trust. */
export function HowItWorks() {
  return (
    // The link in the header goes to this id.
    <section id="how" aria-labelledby="how-title" className="flex flex-col gap-7 border-t pt-10">
      <h2 id="how-title" className="font-display text-4xl font-bold tracking-[0.02em] uppercase">
        How it works
      </h2>
      <ol className="grid grid-cols-[repeat(auto-fit,minmax(min(260px,100%),1fr))] gap-5">
        {CARDS.map(({ icon: Icon, title, text }, index) => (
          <li key={title} className="flex flex-col gap-2.5 rounded-lg border bg-card p-6">
            <div className="flex items-center gap-3">
              <span className="font-display text-[32px] leading-none font-extrabold text-brand">
                {String(index + 1).padStart(2, "0")}
              </span>
              <Icon aria-hidden="true" className="size-6 text-foreground-2" strokeWidth={1.6} />
            </div>
            <h3 className="font-display text-2xl font-bold uppercase">{title}</h3>
            <p className="text-foreground-2">{text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
