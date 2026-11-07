export type ApiStatus = "checking" | "online" | "offline";

// A health probe that hangs is the same to a visitor as an API that is down.
const TIMEOUT_MS = 5000;

/**
 * Asks the analyst API whether it is up. Every failure is "offline": the footer
 * only shows the state, so it has no use for the reason.
 */
export async function checkHealth(
  apiUrl: string | undefined,
  fetchImpl: typeof fetch = fetch,
): Promise<Exclude<ApiStatus, "checking">> {
  if (!apiUrl) return "offline";
  try {
    const response = await fetchImpl(`${apiUrl}/api/health`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
      cache: "no-store",
    });
    if (!response.ok) return "offline";
    const body: unknown = await response.json();
    return typeof body === "object" && body !== null && "status" in body && body.status === "ok"
      ? "online"
      : "offline";
  } catch {
    return "offline";
  }
}
