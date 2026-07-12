import { describe, expect, it, vi } from "vitest";
import { reconnectDelayMs, streamGenerationAfterError } from "./use-run-stream";

describe("SSE reconnect policy", () => {
  it("advances generation so React creates a replacement EventSource", () => {
    expect(streamGenerationAfterError(0)).toBe(1);
    expect(streamGenerationAfterError(4)).toBe(5);
  });

  it("uses bounded exponential backoff", () => {
    expect(reconnectDelayMs(0, () => 0)).toBe(1000);
    expect(reconnectDelayMs(3, () => 0)).toBe(8000);
    expect(reconnectDelayMs(20, () => 0)).toBe(30000);
  });
});
