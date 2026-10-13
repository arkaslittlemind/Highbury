import { CircleAlert } from "lucide-react";

export function CaveatNote({ title, text }: { title: string; text: string }) {
  return (
    <div className="flex gap-3 rounded-panel border border-caveat-line bg-caveat-bg px-5 py-4">
      <CircleAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-caveat" />
      <div className="flex flex-col gap-1">
        <strong className="text-caveat-strong">{title}</strong>
        <span className="text-caveat-text">{text}</span>
      </div>
    </div>
  );
}
