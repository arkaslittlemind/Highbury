"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type RevealProps = {
  children: ReactNode;
  className?: string;
  // Milliseconds. Items of one row get a small step, so they arrive one by one.
  delay?: number;
};

/**
 * Shows its content with a short motion when the visitor scrolls to it, one
 * time. The content is hidden only after the browser says that it is below the
 * screen. So content that is in view at the start does not move, and a page
 * with no JavaScript shows all of it.
 */
export function Reveal({ children, className, delay = 0 }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"static" | "waiting" | "shown">("static");

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) {
          setState("waiting");
          return;
        }
        setState((current) => (current === "waiting" ? "shown" : current));
        observer.disconnect();
      },
      // The motion starts when the content is a small distance inside the screen.
      { rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      data-reveal={state}
      // The step comes from the place of the item in its row, so it cannot be a class.
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
      // With reduced motion the content is never hidden.
      className={cn(
        "data-[reveal=shown]:transition-[opacity,translate] data-[reveal=shown]:duration-700 data-[reveal=shown]:ease-out-strong motion-safe:data-[reveal=waiting]:translate-y-4 motion-safe:data-[reveal=waiting]:opacity-0",
        className,
      )}
    >
      {children}
    </div>
  );
}
