import { Reveal } from "@/components/ask/reveal";

type SectionHeadProps = {
  // The id that the section names in aria-labelledby.
  id: string;
  // The second line is in italic, on its own line.
  headline: readonly [string, string];
  lead: string;
};

/** The centred head of a landing section: a two-line headline and one lead line. */
export function SectionHead({ id, headline, lead }: SectionHeadProps) {
  return (
    <Reveal className="mx-auto mb-12 grid max-w-[640px] gap-3.5 text-center max-[860px]:mb-10">
      <h2
        id={id}
        className="font-display text-[clamp(32px,3.6vw,48px)] leading-[1.04] font-semibold font-stretch-semi-expanded text-balance"
      >
        {headline[0]}
        <em className="block">{headline[1]}</em>
      </h2>
      <p className="text-[17px] text-muted-foreground">{lead}</p>
    </Reveal>
  );
}
