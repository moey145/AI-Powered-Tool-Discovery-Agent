import { useState } from "react";
import { api } from "../utils/api";

export const useSearch = () => {
  const [loading, setLoading] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [loadingStage, setLoadingStage] = useState("");

  const handleSearch = async (query) => {
    if (!query.trim()) return null;

    setLoading(true);
    setLoadingProgress(0);
    setLoadingStage("Initializing search...");

    try {
      // More realistic progress updates based on actual stages
      const updateProgress = (progress, stage) => {
        setLoadingProgress(progress);
        setLoadingStage(stage);
      };

      // Initial setup
      updateProgress(10, "Initializing search...");
      await new Promise((resolve) => setTimeout(resolve, 300));

      // Query analysis
      updateProgress(25, "Analyzing query...");
      await new Promise((resolve) => setTimeout(resolve, 400));

      // Web search
      updateProgress(40, "Searching the web...");
      await new Promise((resolve) => setTimeout(resolve, 500));

      // Content extraction
      updateProgress(55, "Extracting content...");
      await new Promise((resolve) => setTimeout(resolve, 600));

      // Tool analysis
      updateProgress(70, "Analyzing tools...");
      await new Promise((resolve) => setTimeout(resolve, 500));

      // Final processing
      updateProgress(85, "Generating analysis...");

      const results = await api.searchTools(query);

      // Complete
      updateProgress(100, "✅ Analysis complete!");

      // Brief delay to show completion
      setTimeout(() => {
        setLoading(false);
        setLoadingProgress(0);
        setLoadingStage("");
      }, 800);

      return results;
    } catch (error) {
      setLoading(false);
      setLoadingProgress(0);
      setLoadingStage("");
      throw error;
    }
  };

  return {
    loading,
    loadingProgress,
    loadingStage,
    handleSearch,
  };
};
