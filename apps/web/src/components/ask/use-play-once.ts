"use client";

import { useCallback, useEffect, useRef, useState, type PointerEvent } from "react";

/**
 * Plays the build-up of a card once: a mouse that enters it, a focus that comes into
 * it, or, on a touch screen, the card half in view. A play that runs is not
 * restarted, so a pointer that crosses a card twice does not make it flicker. With
 * reduced motion nothing plays. The play ends after playMs, the end of the longest
 * build-up of the card: a timer is simpler than counting animationend events.
 */
export function usePlayOnce(playMs: number) {
  const ref = useRef<HTMLElement>(null);
  const [playing, setPlaying] = useState(false);
  const busy = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const play = useCallback(() => {
    if (busy.current || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    busy.current = true;
    setPlaying(true);
    timer.current = setTimeout(() => {
      busy.current = false;
      setPlaying(false);
    }, playMs);
  }, [playMs]);

  useEffect(() => {
    const element = ref.current;
    let observer: IntersectionObserver | undefined;
    // A touch screen has no hover: the card plays once when it comes into view.
    if (element && !matchMedia("(hover: hover) and (pointer: fine)").matches) {
      observer = new IntersectionObserver(
        ([entry]) => {
          if (!entry.isIntersecting) return;
          play();
          observer?.disconnect();
        },
        { threshold: 0.5 },
      );
      observer.observe(element);
    }
    return () => {
      observer?.disconnect();
      clearTimeout(timer.current);
    };
  }, [play]);

  return {
    ref,
    playing,
    onPointerEnter: (event: PointerEvent) => {
      if (event.pointerType === "mouse") play();
    },
    onFocus: play,
  };
}
