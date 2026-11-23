"use client";

import dynamic from "next/dynamic";
import { useCallback, useRef, useState, type FocusEvent, type KeyboardEvent } from "react";

import { ChartTitle } from "@/components/charts/chart-title";
import type { TimelineApi } from "@/components/charts/xg-timeline-canvas";
import { nextIndex } from "@/lib/shot-map";
import { markOrder, shotLabel, summaryText, type XgTimelineSpec } from "@/lib/xg-timeline";

// ECharts needs the window and is large, so it loads in its own chunk, only where a
// timeline shows. The box around it has the final size, so the page does not jump.
const XgTimelineCanvas = dynamic(() => import("@/components/charts/xg-timeline-canvas"), {
  ssr: false,
  loading: () => null,
});

const STROKE = { strokeWidth: 1.5, vectorEffect: "non-scaling-stroke" } as const;
// The opponent's line is dashed, so the team shows by more than its colour.
const DASH = "6 4";

// Arsenal (team 0) is the brand colour and the opponent is the text colour.
const TEAM_STROKE = ["stroke-brand", "stroke-foreground"];

function Legend({ chart }: { chart: XgTimelineSpec }) {
  return (
    <ul
      aria-label="Legend"
      className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-foreground-2"
    >
      {chart.teams.map((team, index) => (
        <li key={team.team} className="flex min-h-target items-center gap-2">
          <svg aria-hidden="true" width="28" height="10" viewBox="0 0 28 10">
            <line
              x1="1"
              y1="5"
              x2="27"
              y2="5"
              strokeWidth="2.5"
              strokeDasharray={index === 1 ? DASH : undefined}
              className={TEAM_STROKE[index]}
            />
          </svg>
          <span>
            {team.team} <span className="font-semibold text-foreground">{team.xg.toFixed(2)}</span>{" "}
            xG
          </span>
        </li>
      ))}
      <li className="flex min-h-target items-center gap-2">
        <svg aria-hidden="true" width="16" height="16" viewBox="-8 -8 16 16">
          <circle r="6" className="fill-foreground stroke-background" {...STROKE} />
        </svg>
        Goal
      </li>
      <li className="flex min-h-target items-center gap-2">
        <svg aria-hidden="true" width="16" height="16" viewBox="-8 -8 16 16">
          <circle r="3.5" className="fill-surface-chart stroke-foreground" {...STROKE} />
        </svg>
        Shot
      </li>
    </ul>
  );
}

/**
 * The cumulative xG of both teams in one match, as stepped areas by minute, with a
 * mark at each shot. It goes inside the figure of ChartPanel. The chart is one tab
 * stop: the arrow keys move between the shots in minute order, show each one's
 * tooltip, and a live region reads it.
 */
export function XgTimeline({ chart }: { chart: XgTimelineSpec }) {
  const api = useRef<TimelineApi | null>(null);
  // The mark that the keyboard is on.
  const [active, setActive] = useState(0);
  const [announcement, setAnnouncement] = useState("");
  // Stable, so the memoized canvas does not render again on each arrow key.
  const onReady = useCallback((ready: TimelineApi | null) => {
    api.current = ready;
  }, []);

  const marks = markOrder(chart);
  if (marks.length === 0) {
    return (
      <>
        <ChartTitle>{chart.title}</ChartTitle>
        <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
          This chart has no shots.
        </figcaption>
      </>
    );
  }

  function showMark(index: number) {
    setActive(index);
    api.current?.show(index);
    setAnnouncement(shotLabel(marks[index]));
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      api.current?.hide();
      return;
    }
    const next = nextIndex(event.key, active, marks.length);
    if (next === null) return;
    // An arrow key must not scroll the page.
    event.preventDefault();
    showMark(next);
  }

  function onFocus(event: FocusEvent<HTMLDivElement>) {
    // A click gives the focus too, and the pointer then has its own tooltip.
    if (event.currentTarget.matches(":focus-visible")) showMark(active);
  }

  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <ChartTitle>{chart.title}</ChartTitle>
        <span className="text-sm text-muted-foreground">Cumulative xG by minute</span>
      </div>
      <div
        role="group"
        tabIndex={0}
        aria-label={`${chart.title}. ${marks.length} ${marks.length === 1 ? "shot" : "shots"}. Use the arrow keys to move between the shots.`}
        onKeyDown={onKeyDown}
        onFocus={onFocus}
        onBlur={() => api.current?.hide()}
        className="aspect-[15/8] w-full rounded-md outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
      >
        <XgTimelineCanvas chart={chart} onReady={onReady} />
      </div>
      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>
      <Legend chart={chart} />
      <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
        <strong className="text-foreground">Chart summary.</strong> {summaryText(chart)}
      </figcaption>
    </>
  );
}
