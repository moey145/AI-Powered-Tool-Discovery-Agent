const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(message, type = "api", status) {
    super(message);
    this.name = "ApiError";
    this.type = type;
    this.status = status;
  }
}

/** Returns a function that accepts stream text and calls onEvent for each complete event. */
export function createSSEParser(onEvent) {
  let buffer = "";
  return (chunk) => {
    buffer += chunk;
    const frames = buffer.split("\n\n");
    buffer = frames.pop();
    for (const frame of frames) {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice(6))
        .join("\n");
      if (data) onEvent(JSON.parse(data));
    }
  };
}

async function errorFromResponse(response) {
  let detail;
  try {
    detail = (await response.json()).detail;
  } catch {
    detail = undefined;
  }
  if (response.status === 422) {
    const message = Array.isArray(detail)
      ? detail[0]?.msg?.replace(/^Value error, /, "")
      : detail;
    return new ApiError(message || "Please check your input.", "validation", 422);
  }
  const message =
    typeof detail === "string" ? detail : "Something went wrong. Please try again.";
  return new ApiError(message, "api", response.status);
}

/** Runs a search, reporting real backend progress, and resolves with the final result. */
export async function searchTools(query, { onProgress, signal } = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/research/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
      signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(
      "Could not reach the server. Please check your connection and try again.",
      "network"
    );
  }
  if (!response.ok) throw await errorFromResponse(response);

  let result = null;
  const parse = createSSEParser((event) => {
    if (event.type === "progress") onProgress?.(event);
    else if (event.type === "result") result = event.result;
    else if (event.type === "error") throw new ApiError(event.message);
  });

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      parse(value);
    }
  } catch (error) {
    if (error instanceof ApiError || error.name === "AbortError") throw error;
    throw new ApiError("The connection was lost. Please try again.", "network");
  }

  if (!result) throw new ApiError("The connection was lost. Please try again.", "network");
  return result;
}
