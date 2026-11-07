import { describe, expect, it, vi } from "vitest";

import { checkHealth } from "@/lib/api-status";

const API = "https://api.example.test";

function answer(body: unknown, status = 200): typeof fetch {
  return vi.fn(async () => new Response(JSON.stringify(body), { status }));
}

describe("checkHealth", () => {
  it("is online when the API answers status ok", async () => {
    const fetchImpl = answer({ status: "ok" });
    await expect(checkHealth(API, fetchImpl)).resolves.toBe("online");
    expect(fetchImpl).toHaveBeenCalledWith(`${API}/api/health`, expect.anything());
  });

  it("is offline when the body is not status ok", async () => {
    await expect(checkHealth(API, answer({ status: "starting" }))).resolves.toBe("offline");
    await expect(checkHealth(API, answer("ok"))).resolves.toBe("offline");
  });

  it("is offline when the status code is not 2xx", async () => {
    await expect(checkHealth(API, answer({ status: "ok" }, 503))).resolves.toBe("offline");
  });

  it("is offline when the request throws, as on a network error or a timeout", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new DOMException("The operation timed out.", "TimeoutError");
    });
    await expect(checkHealth(API, fetchImpl)).resolves.toBe("offline");
  });

  it("is offline when the body is not JSON", async () => {
    const fetchImpl = vi.fn(async () => new Response("<html>", { status: 200 }));
    await expect(checkHealth(API, fetchImpl)).resolves.toBe("offline");
  });

  it("is offline with no API URL, and does not call fetch", async () => {
    const fetchImpl = answer({ status: "ok" });
    await expect(checkHealth(undefined, fetchImpl)).resolves.toBe("offline");
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
