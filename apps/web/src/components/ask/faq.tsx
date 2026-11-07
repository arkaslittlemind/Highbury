import styles from "@/components/ask/faq.module.css";
import { Reveal } from "@/components/ask/reveal";
import { FAQ } from "@/lib/landing-content";
import { cn } from "@/lib/utils";

/**
 * The questions a visitor asks before the first question. Each answer is a native
 * details element, so the browser gives it the keyboard (Tab, then Enter or
 * Space) and the open state to screen readers with no script.
 */
export function Faq() {
  return (
    <section
      aria-labelledby="faq-title"
      className={cn(styles.faq, "mx-auto w-full max-w-[960px] pt-10 pb-32 max-[600px]:pb-24")}
    >
      <Reveal className="mb-6 grid gap-3.5 text-center">
        <h2
          id="faq-title"
          className="font-display text-[clamp(32px,3.6vw,48px)] leading-[1.04] font-semibold font-stretch-semi-expanded text-balance"
        >
          {FAQ.headline}
        </h2>
        <p className="text-[17px] text-muted-foreground">{FAQ.lead}</p>
      </Reveal>
      {FAQ.groups.map((group) => (
        <div key={group.title}>
          <h3 className="mt-14 mb-2 text-center font-display text-[22px] leading-[1.2] font-semibold font-stretch-semi-expanded max-[600px]:mt-10">
            {group.title}
          </h3>
          {group.items.map((item) => (
            <details key={item.question} className={cn(styles.qa, "border-b border-border")}>
              <summary className="flex min-h-[84px] cursor-pointer items-center justify-between gap-6 rounded-md py-4.5 text-[clamp(18px,1.6vw,21px)] leading-[1.35] font-medium focus-visible:outline-offset-6 max-[600px]:min-h-[72px]">
                {item.question}
                <span aria-hidden="true" className={styles.pm} />
              </summary>
              <div className="grid max-w-[68ch] gap-2.5 pr-14 pb-6.5 text-base leading-[1.65] text-foreground-2 max-[600px]:pr-0">
                {item.answer.map((paragraph) => (
                  <p key={paragraph}>{paragraph}</p>
                ))}
              </div>
            </details>
          ))}
        </div>
      ))}
    </section>
  );
}
