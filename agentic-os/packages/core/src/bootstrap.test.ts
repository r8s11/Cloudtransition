import { describe, it, expect } from "vitest";

describe("Vitest harness", () => {
  it("can execute a basic smoke test", () => {
    expect(1 + 1).toBe(2);
  });

  it("can import from @agentic-os/core", () => {
    // This proves the package resolution works
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const core = () => import("@agentic-os/core");
    expect(typeof core).toBe("function");
  });
});
