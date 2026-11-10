import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, searchTools } from "../utils/api";
import type { ResearchResult, SearchError, Tool } from "../types";

export const useSearch = () => {
  const [loading, setLoading] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [loadingStage, setLoadingStage] = useState("");
  const [streamedTools, setStreamedTools] = useState<Tool[]>([]);
  const [results, setResults] = useState<ResearchResult | null>(null);
  const [error, setError] = useState<SearchError | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const cancel = useCallback(() => controllerRef.current?.abort(), []);

  const handleSearch = useCallback(async (query: string): Promise<boolean> => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setLoading(true);
    setLoadingProgress(0);
    setLoadingStage("Starting research");
    setStreamedTools([]);
    setResults(null);
    setError(null);

    try {
      const result = await searchTools(query.trim(), {
        signal: controller.signal,
        onProgress: ({ percent, message }) => {
          setLoadingProgress(percent);
          setLoadingStage(message);
        },
        onTool: (tool) => setStreamedTools((tools) => [...tools, tool]),
      });
      setResults(result);
      return true;
    } catch (err) {
      if (err instanceof ApiError) {
        setError({ type: err.type, message: err.message });
      } else if (!(err instanceof Error && err.name === "AbortError")) {
        setError({ type: "api", message: "Something went wrong. Please try again." });
      }
      return false;
    } finally {
      if (controllerRef.current === controller) {
        setLoading(false);
        setLoadingProgress(0);
        setLoadingStage("");
        setStreamedTools([]);
      }
    }
  }, []);

  return {
    loading,
    loadingProgress,
    loadingStage,
    streamedTools,
    results,
    error,
    setError,
    handleSearch,
    cancel,
  };
};
