import type {
  ProgressEvent,
  ResearchResult,
  SearchErrorType,
  StreamEvent,
  Tool,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  type: SearchErrorType;
  status?: number;

  constructor(message: string, type: SearchErrorType = "api", status?: number) {
    super(message);
    this.name = "ApiError";
    this.type = type;
    this.status = status;
  }
}

/** Returns a function that accepts stream text and calls onEvent for each complete event. */
export function createSSEParser(onEvent: (event: StreamEvent) => void) {
  let buffer = "";
  return (chunk: string) => {
    buffer += chunk;
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice(6))
        .join("\n");
      if (data) onEvent(JSON.parse(data) as StreamEvent);
    }
  };
}

export function formatWait(seconds: number): string {
  if (seconds < 90) return `${seconds} second${seconds === 1 ? "" : "s"}`;
  if (seconds < 5400) return `${Math.ceil(seconds / 60)} minutes`;
  return `${Math.ceil(seconds / 3600)} hours`;
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  let detail: unknown;
  try {
    detail = ((await response.json()) as { detail?: unknown }).detail;
  } catch {
    detail = undefined;
  }
  if (response.status === 422) {
    const first = Array.isArray(detail) ? (detail[0] as { msg?: string } | undefined) : undefined;
    const message = first?.msg?.replace(/^Value error, /, "");
    return new ApiError(message || "Please check your input.", "validation", 422);
  }
  if (response.status === 429) {
    const seconds = Number(response.headers.get("Retry-After"));
    const wait = seconds > 0 ? ` Try again in ${formatWait(seconds)}.` : "";
    return new ApiError(`You've reached the search limit.${wait}`, "api", 429);
  }
  const message = typeof detail === "string" ? detail : "Something went wrong. Please try again.";
  return new ApiError(message, "api", response.status);
}

interface SearchOptions {
  onProgress?: (event: ProgressEvent) => void;
  onTool?: (tool: Tool) => void;
  signal?: AbortSignal;
}

export const isAbort = (error: unknown) =>
  typeof error === "object" && error !== null && (error as { name?: unknown }).name === "AbortError";

/** Rejects when the signal aborts. Browsers don't reliably end a piped body stream on abort. */
function whenAborted(signal?: AbortSignal): { promise: Promise<never>; dispose: () => void } {
  if (!signal) return { promise: new Promise<never>(() => {}), dispose: () => {} };
  let onAbort = () => {};
  const promise = new Promise<never>((_, reject) => {
    onAbort = () => reject(new DOMException("The search was cancelled.", "AbortError"));
    if (signal.aborted) onAbort();
    else signal.addEventListener("abort", onAbort, { once: true });
  });
  promise.catch(() => {}); // Only awaited while reading; never report it as unhandled.
  return { promise, dispose: () => signal.removeEventListener("abort", onAbort) };
}

/** Runs a search, reporting real backend progress, and resolves with the final result. */
export async function searchTools(
  query: string,
  { onProgress, onTool, signal }: SearchOptions = {}
): Promise<ResearchResult> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/research/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
      signal,
    });
  } catch (error) {
    if (isAbort(error)) throw error;
    throw new ApiError(
      "Could not reach the server. Please check your connection and try again.",
      "network"
    );
  }
  if (!response.ok) throw await errorFromResponse(response);

  let result: ResearchResult | null = null;
  const parse = createSSEParser((event) => {
    if (event.type === "progress") onProgress?.(event);
    else if (event.type === "tool") onTool?.(event.company);
    else if (event.type === "result") result = event.result;
    else if (event.type === "error") throw new ApiError(event.message);
  });

  if (!response.body) throw new ApiError("The connection was lost. Please try again.", "network");
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  const aborted = whenAborted(signal);
  try {
    for (;;) {
      const { value, done } = await Promise.race([reader.read(), aborted.promise]);
      if (done) break;
      parse(value);
    }
  } catch (error) {
    reader.cancel().catch(() => {});
    if (error instanceof ApiError || isAbort(error)) throw error;
    throw new ApiError("The connection was lost. Please try again.", "network");
  } finally {
    aborted.dispose();
  }

  if (!result) throw new ApiError("The connection was lost. Please try again.", "network");
  return result;
}
