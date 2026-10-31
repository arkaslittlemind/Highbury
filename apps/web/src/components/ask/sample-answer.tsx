import { pill } from "@/components/ask/pill";
import { Reveal } from "@/components/ask/reveal";
import { SectionTag } from "@/components/ask/section-tag";
import { ShotMap } from "@/components/charts/shot-map";
import { SAMPLE_SHOT_MAP } from "@/lib/sample-shots";
import { cn } from "@/lib/utils";

type SampleAnswerProps = {
  // Asks the question of a full answer. With no question to ask, the button is not shown.
  onSeeAnswer?: () => void;
};

/** One chart of an answer, as the page draws it. A visitor can use it before a question. */
export function SampleAnswer({ onSeeAnswer }: SampleAnswerProps) {
  return (
    <section
      id="sample"
      aria-labelledby="sample-title"
      className="flex scroll-mt-6 flex-wrap items-center justify-between gap-x-12 gap-y-8 pt-6 pb-16 sm:pb-24"
    >
      <Reveal className="flex min-w-0 flex-[1_1_340px] flex-col gap-5">
        <SectionTag>Sample answer</SectionTag>
        <h2
          id="sample-title"
          className="font-display text-[40px] leading-none font-semibold text-balance sm:text-[64px]"
        >
          The chart is <em>the answer.</em>
        </h2>
        <p className="max-w-[420px] text-[17px] text-foreground-2">
          A shot map where size is xG and shape is the outcome. Comparison bars that use only
          the metrics that the two seasons share. A summary in words under every chart.
        </p>
        {onSeeAnswer && (
          <button type="button" onClick={onSeeAnswer} className={cn(pill, "self-start")}>
            See a full answer
          </button>
        )}
      </Reveal>
      {/* The pitch is tall, so the chart does not take the full width. */}
      <Reveal delay={70} className="max-w-[680px] min-w-0 flex-[999_1_520px]">
        <figure className="flex flex-col gap-4 rounded-3xl border border-line-mid bg-linear-165 from-grass-700 via-grass-850 via-55% to-surface-chart p-5 sm:p-7">
          <ShotMap chart={SAMPLE_SHOT_MAP} />
        </figure>
      </Reveal>
    </section>
  );
}
