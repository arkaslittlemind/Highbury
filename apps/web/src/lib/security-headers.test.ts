import { describe, expect, it } from "vitest";

import { buildCsp, securityHeaders } from "@/lib/security-headers";

// The value of one directive, for example "connect-src 'self' https://api.test".
function directive(csp: string, name: string): string | undefined {
  return csp
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.split(" ")[0] === name);
}

describe("buildCsp", () => {
  it("lets the page call the origin of the API, with no path", () => {
    const csp = buildCsp({ apiUrl: "https://api.example.com/some/path/", dev: false });
    expect(directive(csp, "connect-src")).toBe("connect-src 'self' https://api.example.com");
  });

  it("allows only the site itself when the API URL is missing or not a URL", () => {
    expect(directive(buildCsp({ apiUrl: undefined, dev: false }), "connect-src")).toBe(
      "connect-src 'self'",
    );
    expect(directive(buildCsp({ apiUrl: "not a url", dev: false }), "connect-src")).toBe(
      "connect-src 'self'",
    );
  });

  it("allows eval only in development", () => {
    const api = "http://localhost:8000";
    expect(directive(buildCsp({ apiUrl: api, dev: true }), "script-src")).toContain(
      "'unsafe-eval'",
    );
    expect(directive(buildCsp({ apiUrl: api, dev: false }), "script-src")).not.toContain(
      "'unsafe-eval'",
    );
  });

  it("allows the Turnstile script and its frame", () => {
    const csp = buildCsp({ apiUrl: "https://api.example.com", dev: false });
    expect(directive(csp, "script-src")).toContain("https://challenges.cloudflare.com");
    expect(directive(csp, "frame-src")).toBe("frame-src https://challenges.cloudflare.com");
  });

  it("allows the Cloudflare Web Analytics script, which reports to the site itself", () => {
    const csp = buildCsp({ apiUrl: "https://api.example.com", dev: false });
    expect(directive(csp, "script-src")).toContain("https://static.cloudflareinsights.com");
    expect(directive(csp, "connect-src")).not.toContain("cloudflareinsights");
  });

  it("denies framing, plugins, and other bases and form targets", () => {
    const csp = buildCsp({ apiUrl: "https://api.example.com", dev: false });
    expect(directive(csp, "frame-ancestors")).toBe("frame-ancestors 'none'");
    expect(directive(csp, "object-src")).toBe("object-src 'none'");
    expect(directive(csp, "base-uri")).toBe("base-uri 'self'");
    expect(directive(csp, "form-action")).toBe("form-action 'self'");
    expect(directive(csp, "default-src")).toBe("default-src 'self'");
  });
});

describe("securityHeaders", () => {
  it("sends the CSP and the four other headers", () => {
    const headers = Object.fromEntries(
      securityHeaders({ apiUrl: "https://api.example.com", dev: false }).map((h) => [
        h.key,
        h.value,
      ]),
    );
    expect(headers["Content-Security-Policy"]).toContain(
      "connect-src 'self' https://api.example.com",
    );
    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
    expect(headers["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["X-Frame-Options"]).toBe("DENY");
    expect(headers["Permissions-Policy"]).toBe(
      "camera=(), microphone=(), geolocation=(), payment=()",
    );
  });
});
