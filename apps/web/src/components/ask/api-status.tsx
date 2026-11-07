"use client";

import { useEffect, useState } from "react";

import { type ApiStatus as Status, checkHealth } from "@/lib/api-status";
import { cn } from "@/lib/utils";

const TEXT: Record<Status, string> = {
  checking: "Checking the analyst",
  online: "The analyst is online",
  offline: "The analyst is offline",
};

// The dot is decorative: the text says the state.
const DOT: Record<Status, string> = {
  checking: "bg-faint shadow-[0_0_0_4px_var(--line-subtle)]",
  online: "bg-verified shadow-[0_0_0_4px_var(--verified-bg)]",
  offline: "bg-brand shadow-[0_0_0_4px_var(--now-900)]",
};

/**
 * The live state of the analyst API, asked once when the page opens. The page is
 * prerendered, so the state must come from the browser and not the server.
 */
export function ApiStatus({ apiUrl }: { apiUrl: string | undefined }) {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let current = true;
    checkHealth(apiUrl).then((result) => {
      if (current) setStatus(result);
    });
    return () => {
      current = false;
    };
  }, [apiUrl]);

  return (
    <span className="mt-2 inline-flex items-center gap-2.5 text-[15px] text-foreground-2">
      <i aria-hidden="true" className={cn("size-2.5 rounded-full", DOT[status])} />
      {TEXT[status]}
    </span>
  );
}
