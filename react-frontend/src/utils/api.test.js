import { describe, expect, it, vi } from "vitest";
import { ApiError, createSSEParser, searchTools } from "./api";

const frame = (event) => `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;

function streamResponse(chunks, init) {
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
    const events = [];
    const parse = createSSEParser((event) => events.push(event));
    const text = frame({ type: "progress", percent: 5 });
    parse(text.slice(0, 10));
    expect(events).toEqual([]);
    parse(text.slice(10));
    expect(events).toEqual([{ type: "progress", percent: 5 }]);
  });
});

describe("searchTools", () => {
  it("reports progress and resolves with the result", async () => {
    const result = { companies: [] };
    vi.stubGlobal("fetch", async () =>
      streamResponse([
        frame({ type: "progress", percent: 5, message: "Searching" }),
        frame({ type: "result", result }),
      ])
    );
    const onProgress = vi.fn();
    await expect(searchTools("react", { onProgress })).resolves.toEqual(result);
    expect(onProgress).toHaveBeenCalledOnce();
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

  it("reports network failures", async () => {
    vi.stubGlobal("fetch", async () => {
      throw new TypeError("Failed to fetch");
    });
    await expect(searchTools("react")).rejects.toMatchObject({ type: "network" });
  });
});
