import { CountUp } from "@/components/ask/count-up";
import { LANDING_DATA } from "@/lib/landing-data";

const RESULTS_URL = "https://github.com/arkaslittlemind/Highbury/blob/main/evals/results.md";

/** "2026-11-01" as "1 Nov 2026". The date is a calendar day, so it is read in UTC. */
function dayText(isoDay: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${isoDay}T00:00:00Z`));
}

/** The eval numbers of the production model: how well the analyst answers the golden questions. */
export function ProofBand() {
  const proof = LANDING_DATA.proof;
  const numbers = [
    {
      value: proof.correct,
      of: `/ ${proof.correctTotal}`,
      label: "Golden questions answered correctly",
    },
    { value: proof.verifiedRate ?? 0, of: "%", label: "Of claims verified against the data" },
    // The evals count questions that the data cannot answer and questions out of scope.
    { value: proof.refusals, of: `/ ${proof.refusalTotal}`, label: "Unanswerable questions declined" },
    { value: proof.chartMatches, of: `/ ${proof.chartTotal}`, label: "Charts of the right type" },
  ];
  return (
    <section aria-labelledby="proof-title" className="mx-auto w-full max-w-[1200px] pb-30 max-[600px]:pb-22">
      <h2 id="proof-title" className="sr-only">
        How well it answers
      </h2>
      <div className="grid gap-7 rounded-[18px] border border-verified-line bg-[radial-gradient(120%_140%_at_50%_0%,color-mix(in_srgb,var(--verified-bg)_90%,transparent),var(--card))] px-12 py-10 max-[600px]:px-5 max-[600px]:py-7">
        <ul className="grid grid-cols-4 gap-6 max-[960px]:grid-cols-2 max-[960px]:gap-y-7">
          {numbers.map(({ value, of, label }) => (
            <li
              key={label}
              className="grid content-start gap-2 border-l border-verified-line pl-5 max-[600px]:pl-3.5"
            >
              <b className="font-display text-[clamp(30px,3.2vw,42px)] leading-none font-bold font-stretch-semi-expanded">
                <CountUp value={value} />
                <small className="ml-1 text-[max(14px,0.5em)] font-semibold text-verified">{of}</small>
              </b>
              <span className="text-[15px] leading-[1.4] text-foreground-2">{label}</span>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-verified-line pt-5.5 text-[14.5px] text-muted-foreground">
          <p>
            Each golden question has hand-written SQL and expected values. Last run{" "}
            {dayText(proof.runDate)} on{" "}
            <code className="font-mono text-[13px] text-foreground-2">{proof.model}</code>.
          </p>
          <a
            href={RESULTS_URL}
            className="group inline-flex min-h-target items-center gap-2 font-semibold text-foreground"
          >
            See every question
            <span
              aria-hidden="true"
              className="transition-transform duration-200 ease-out-strong group-hover:translate-x-[3px]"
            >
              →
            </span>
          </a>
        </div>
      </div>
    </section>
  );
}
