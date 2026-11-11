import { describe, expect, it, vi } from "vitest";
import { ApiError, createSSEParser, formatWait, searchTools } from "./api";
import type { StreamEvent, Tool } from "../types";

const frame = (event: object) =>
  `event: ${(event as { type: string }).type}\ndata: ${JSON.stringify(event)}\n\n`;

function streamResponse(chunks: string[], init?: ResponseInit) {
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
  return new Response(body, init);
}

describe("createSSEParser", () => {
  it("handles events split across chunks", () => {
    const events: StreamEvent[] = [];
    const parse = createSSEParser((event) => events.push(event));
    const text = frame({ type: "progress", percent: 5 });
    parse(text.slice(0, 10));
    expect(events).toEqual([]);
    parse(text.slice(10));
    expect(events).toEqual([{ type: "progress", percent: 5 }]);
  });
});

describe("formatWait", () => {
  it.each([
    [1, "1 second"],
    [42, "42 seconds"],
    [300, "5 minutes"],
    [7200, "2 hours"],
  ])("formats %i", (seconds, expected) => {
    expect(formatWait(seconds)).toBe(expected);
  });
});

describe("searchTools", () => {
  it("reports progress and tools, and resolves with the result", async () => {
    const result = { companies: [] };
    const tool = { name: "Redux" };
    vi.stubGlobal("fetch", async () =>
      streamResponse([
        frame({ type: "progress", percent: 5, message: "Searching" }),
        frame({ type: "tool", company: tool }),
        frame({ type: "result", result }),
      ])
    );
    const onProgress = vi.fn();
    const onTool = vi.fn<(tool: Tool) => void>();
    await expect(searchTools("react", { onProgress, onTool })).resolves.toEqual(result);
    expect(onProgress).toHaveBeenCalledOnce();
    expect(onTool).toHaveBeenCalledWith(tool);
  });

  it("surfaces server-sent errors", async () => {
    vi.stubGlobal("fetch", async () =>
      streamResponse([frame({ type: "error", message: "Took too long" })])
    );
    await expect(searchTools("react")).rejects.toThrow("Took too long");
  });

  it("treats a stream that ends without a result as an error", async () => {
    vi.stubGlobal("fetch", async () => streamResponse([]));
    await expect(searchTools("react")).rejects.toBeInstanceOf(ApiError);
  });

  it("reads validation messages from 422 responses", async () => {
    vi.stubGlobal("fetch", async () =>
      Response.json(
        { detail: [{ msg: "Value error, Query must be at least 2 characters long" }] },
        { status: 422 }
      )
    );
    await expect(searchTools("a")).rejects.toMatchObject({
      type: "validation",
      message: "Query must be at least 2 characters long",
    });
  });

  it("tells users how long to wait when rate limited", async () => {
    vi.stubGlobal("fetch", async () =>
      Response.json({ detail: "Too many" }, { status: 429, headers: { "Retry-After": "42" } })
    );
    await expect(searchTools("react")).rejects.toThrow("Try again in 42 seconds.");
  });

  it("stops promptly on cancel even if the stream never ends", async () => {
    const encoder = new TextEncoder();
    // A body that sends one event and then hangs, like a browser that ignores the abort.
    const hanging = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(frame({ type: "progress", percent: 5, message: "x" })));
      },
    });
    vi.stubGlobal("fetch", async () => new Response(hanging));
    const controller = new AbortController();
    const search = searchTools("react", { signal: controller.signal, onProgress: () => controller.abort() });
    await expect(search).rejects.toMatchObject({ name: "AbortError" });
  });

  it("rejects immediately if already cancelled", async () => {
    vi.stubGlobal("fetch", async () => new Response(new ReadableStream({ start() {} })));
    const controller = new AbortController();
    controller.abort();
    await expect(searchTools("react", { signal: controller.signal })).rejects.toMatchObject({
      name: "AbortError",
    });
  });

  it("reports network failures", async () => {
    vi.stubGlobal("fetch", async () => {
      throw new TypeError("Failed to fetch");
    });
    await expect(searchTools("react")).rejects.toMatchObject({ type: "network" });
  });
});
