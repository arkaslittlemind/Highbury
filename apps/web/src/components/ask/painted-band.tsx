import Image, { type StaticImageData } from "next/image";
import type { ReactNode } from "react";

import styles from "@/components/ask/painted-band.module.css";
import { cn } from "@/lib/utils";

// The column of the landing sections: the same width and side padding as the
// sections between the bands, so a band changes the background only.
export const LANDING_COLUMN = "mx-auto flex w-full max-w-[1360px] flex-col px-4 sm:px-10";

type PaintedBandProps = {
  children: ReactNode;
  // The painting behind the section. With none, the band is only the column.
  painting?: StaticImageData;
  // "cover" fills the band and fades at both edges. "top" sits at the top of a
  // tall band and fades out, so the lower part of the section is on the plain page.
  fit?: "cover" | "top";
  // The part of the painting that a narrow screen keeps: an object-position
  // class such as "object-[50%_40%]", so the value stays a Tailwind class.
  focus?: string;
};

/**
 * A full-width band behind one landing section. The band is as wide as its
 * parent, never 100vw: 100vw counts the scrollbar on Windows and would scroll
 * the page sideways. The painting is decorative and absolutely positioned, so
 * the band's height comes from the section and a late image load cannot move it.
 */
export function PaintedBand({ children, painting, fit = "cover", focus = "object-center" }: PaintedBandProps) {
  return (
    // overflow-clip keeps a tall "top" painting out of the next section; clip, not
    // hidden, so the band does not become a scroll container.
    <div className="relative isolate w-full overflow-clip">
      {painting && (
        <div aria-hidden="true" className={cn(styles.art, fit === "top" ? styles.top : styles.cover)}>
          <Image
            src={painting}
            alt=""
            fill
            sizes="100vw"
            className={cn("object-cover", focus)}
          />
        </div>
      )}
      <div className={LANDING_COLUMN}>{children}</div>
    </div>
  );
}
