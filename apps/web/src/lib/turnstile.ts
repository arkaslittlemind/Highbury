/** After this wait the page says that it checks the browser. */
export const SLOW_MS = 2_000;
/** With no token after this wait, the question goes out with none and the API refuses it. */
export const TIMEOUT_MS = 10_000;

export type TokenWait = {
  /** The token, or null when the check failed or ran out of time. */
  token: Promise<string | null>;
  /** Give the result. Only the first one counts. */
  settle: (token: string | null) => void;
  /** Stop the time limit while Cloudflare shows the visitor a checkbox. */
  pause: () => void;
  /** Start the time limit again, in full, after the checkbox. */
  resume: () => void;
};

/** Wait for one Turnstile token, with a time limit and a sign when it is slow. */
export function waitForToken(onSlow: () => void): TokenWait {
  let resolve: (token: string | null) => void = () => {};
  const token = new Promise<string | null>((done) => {
    resolve = done;
  });
  let settled = false;
  let limit: ReturnType<typeof setTimeout> | undefined;

  const settle = (value: string | null) => {
    if (settled) return;
    settled = true;
    clearTimeout(slow);
    clearTimeout(limit);
    resolve(value);
  };
  const resume = () => {
    clearTimeout(limit);
    if (!settled) limit = setTimeout(() => settle(null), TIMEOUT_MS);
  };
  // The sign stays on a timer of its own: a visitor with a checkbox waits too.
  const slow = setTimeout(onSlow, SLOW_MS);
  resume();

  return { token, settle, pause: () => clearTimeout(limit), resume };
}
