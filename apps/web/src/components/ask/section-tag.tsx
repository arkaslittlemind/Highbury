/** The small label above the heading of a section of the landing screen. */
export function SectionTag({ children }: { children: string }) {
  return (
    <span className="self-start rounded-full border border-line-mid px-4 py-1.5 text-sm text-foreground-2">
      {children}
    </span>
  );
}
