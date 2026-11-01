import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SLOW_MS, TIMEOUT_MS, waitForToken } from "@/lib/turnstile";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("waitForToken", () => {
  it("gives the token that comes, and does not say that it is slow", async () => {
    const onSlow = vi.fn();
    const wait = waitForToken(onSlow);
    wait.settle("token-1");
    vi.advanceTimersByTime(TIMEOUT_MS);
    expect(await wait.token).toBe("token-1");
    expect(onSlow).not.toHaveBeenCalled();
  });

  it("says once that it is slow after 2 s", () => {
    const onSlow = vi.fn();
    waitForToken(onSlow);
    vi.advanceTimersByTime(SLOW_MS - 1);
    expect(onSlow).not.toHaveBeenCalled();
    vi.advanceTimersByTime(TIMEOUT_MS);
    expect(onSlow).toHaveBeenCalledTimes(1);
  });

  it("gives null after 10 s with no token", async () => {
    const wait = waitForToken(() => {});
    vi.advanceTimersByTime(TIMEOUT_MS);
    expect(await wait.token).toBeNull();
  });

  it("keeps the first result", async () => {
    const wait = waitForToken(() => {});
    wait.settle(null);
    wait.settle("too-late");
    expect(await wait.token).toBeNull();
  });

  it("does not run out while the visitor has a checkbox to tick", async () => {
    const wait = waitForToken(() => {});
    vi.advanceTimersByTime(TIMEOUT_MS - 1000);
    wait.pause();
    vi.advanceTimersByTime(60_000);
    wait.resume();
    vi.advanceTimersByTime(TIMEOUT_MS - 1);
    wait.settle("ticked");
    expect(await wait.token).toBe("ticked");
  });

  it("runs out 10 s after the checkbox is ticked with no token", async () => {
    const wait = waitForToken(() => {});
    wait.pause();
    wait.resume();
    vi.advanceTimersByTime(TIMEOUT_MS);
    expect(await wait.token).toBeNull();
  });

  it("says that it is slow also when the checkbox comes before 2 s", () => {
    const onSlow = vi.fn();
    const wait = waitForToken(onSlow);
    wait.pause();
    vi.advanceTimersByTime(SLOW_MS);
    expect(onSlow).toHaveBeenCalledTimes(1);
  });
});
