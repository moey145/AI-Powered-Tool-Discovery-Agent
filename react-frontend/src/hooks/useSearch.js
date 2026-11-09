import { useCallback, useEffect, useRef, useState } from "react";
import { searchTools } from "../utils/api";

const COMPLETION_HOLD_MS = 400;
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const useSearch = () => {
  const [loading, setLoading] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [loadingStage, setLoadingStage] = useState("");
  const [error, setError] = useState(null);
  const controllerRef = useRef(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const handleSearch = useCallback(async (query) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setLoading(true);
    setLoadingProgress(0);
    setLoadingStage("Starting research");
    setError(null);

    try {
      const results = await searchTools(query.trim(), {
        signal: controller.signal,
        onProgress: ({ percent, message }) => {
          setLoadingProgress(percent);
          setLoadingStage(message);
        },
      });
      setLoadingProgress(100);
      setLoadingStage("Research complete");
      await wait(COMPLETION_HOLD_MS);
      return results;
    } catch (err) {
      if (err.name !== "AbortError") {
        setError({ type: err.type || "unknown", message: err.message });
      }
      return null;
    } finally {
      if (controllerRef.current === controller) {
        setLoading(false);
        setLoadingProgress(0);
        setLoadingStage("");
      }
    }
  }, []);

  return { loading, loadingProgress, loadingStage, error, setError, handleSearch };
};
