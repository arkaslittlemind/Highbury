export { cn } from "cn"

/**
 * Joins the two years of a season such as 2003-04 with a non-breaking hyphen,
 * so a line of the page never breaks inside a season. Only for the rendered
 * text: the Markdown copies keep the plain hyphen.
 */
export function keepSeasonsWhole(text: string): string {
  return text.replace(/\b(\d{4})-(\d{2})\b/g, "$1‑$2");
}
