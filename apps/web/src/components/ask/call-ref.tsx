import { cn } from "@/lib/utils";

type CallRefProps = {
  // The id of a query, as a claim cites it.
  callId: string;
  // Show the tool call with this id. Absent when the working has no such call.
  onShow?: () => void;
};

const STYLE = "font-mono text-xs text-muted-foreground";

/** The id of the query behind a claim, as a way to its tool call when there is one. */
export function CallRef({ callId, onShow }: CallRefProps) {
  if (!onShow) return <span className={STYLE}>{callId}</span>;
  return (
    <button
      type="button"
      onClick={onShow}
      aria-label={`Show the query ${callId}`}
      className={cn(STYLE, "cursor-pointer underline hover:text-foreground-2")}
    >
      {callId}
    </button>
  );
}
