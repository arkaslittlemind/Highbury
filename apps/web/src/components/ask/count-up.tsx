"use client";

import { useEffect, useRef } from "react";

const DURATION_MS = 900;

/**
 * A number that counts up from 0 once, when half of it comes into view. The final
 * number is in the markup, so a reader with no script sees it. The count starts at 0
 * only when the browser says the number is below the screen: a number that is in view
 * when the page opens does not jump. With reduced motion it never counts.
 */
export function CountUp({ value, digits = 0 }: { value: number; digits?: number }) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const final = value.toFixed(digits);
    let frame = 0;
    let waiting = false;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) {
          // Below the screen: show 0 until the visitor scrolls to it.
          if (entry.boundingClientRect.top > 0) {
            waiting = true;
            element.textContent = (0).toFixed(digits);
          }
          return;
        }
        observer.disconnect();
        if (!waiting) return;
        const start = performance.now();
        const tick = (now: number) => {
          const t = Math.min(1, (now - start) / DURATION_MS);
          // A strong ease-out: the count is quick at first and settles on the number.
          const eased = 1 - (1 - t) ** 3;
          element.textContent = t < 1 ? (value * eased).toFixed(digits) : final;
          if (t < 1) frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
      },
      { threshold: 0.5 },
    );
    observer.observe(element);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      element.textContent = final;
    };
  }, [value, digits]);

  // The text is written in place for each frame, so the count does not render React.
  return (
    <span ref={ref} className="tabular-nums">
      {value.toFixed(digits)}
    </span>
  );
}
