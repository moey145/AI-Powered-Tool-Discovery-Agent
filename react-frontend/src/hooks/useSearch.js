import { useState, useRef } from "react";
import { api } from "../utils/api";

export const useSearch = () => {
  const [loading, setLoading] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [loadingStage, setLoadingStage] = useState("");
  const [error, setError] = useState(null);
  const tickerRef = useRef(null);

  const handleSearch = async (query) => {
    if (!query.trim()) return null;

    // Client-side validation
    if (query.trim().length < 2) {
      setError({
        type: "validation",
        message: "Query must be at least 2 characters long",
        errors: [
          {
            field: "query",
            message: "Query must be at least 2 characters long",
          },
        ],
      });
      return null;
    }

    if (query.length > 200) {
      setError({
        type: "validation",
        message: "Query must be less than 200 characters",
        errors: [
          { field: "query", message: "Query must be less than 200 characters" },
        ],
      });
      return null;
    }

    // Check for potentially dangerous content
    const dangerousPatterns = [
      /<script/i,
      /javascript:/i,
      /data:text\/html/i,
      /vbscript:/i,
      /onload=/i,
      /onerror=/i,
      /<iframe/i,
      /<object/i,
      /<embed/i,
      /<link/i,
      /<meta/i,
      /<style/i,
    ];

    for (const pattern of dangerousPatterns) {
      if (pattern.test(query)) {
        setError({
          type: "validation",
          message: "Query contains potentially dangerous content",
          errors: [
            {
              field: "query",
              message: "Query contains potentially dangerous content",
            },
          ],
        });
        return null;
      }
    }

    // Check for SQL injection patterns
    const sqlPatterns = [
      /union\s+select/i,
      /drop\s+table/i,
      /delete\s+from/i,
      /insert\s+into/i,
      /update\s+set/i,
      /;\s*drop/i,
      /;\s*delete/i,
      /;\s*insert/i,
      /;\s*update/i,
    ];

    for (const pattern of sqlPatterns) {
      if (pattern.test(query)) {
        setError({
          type: "validation",
          message: "Query contains potentially dangerous SQL content",
          errors: [
            {
              field: "query",
              message: "Query contains potentially dangerous SQL content",
            },
          ],
        });
        return null;
      }
    }

    // Check for excessive special characters
    const specialCharCount = (query.match(/[^\w\s]/g) || []).length;
    if (specialCharCount > query.length * 0.3) {
      setError({
        type: "validation",
        message: "Query contains too many special characters",
        errors: [
          {
            field: "query",
            message: "Query contains too many special characters",
          },
        ],
      });
      return null;
    }

    setLoading(true);
    setLoadingProgress(0);
    setLoadingStage("Initializing...");
    setError(null); // Clear any previous errors

    try {
      // More accurate progress based on actual workflow steps
      const startTime = Date.now();
      const maxWhilePendingBase = 92; // base cap; rises over time to avoid "stuck" feel

      // Updated stages based on actual workflow: extract_tools -> research -> analyze
      const stages = [
        {
          t: 800,
          label: "Analyzing query and extracting tools...",
          min: 5,
          max: 25,
          description: "Searching web sources and identifying relevant tools",
        },
        {
          t: 2500,
          label: "Researching individual tools...",
          min: 25,
          max: 65,
          description:
            "Scraping tool websites and gathering detailed information",
        },
        {
          t: 4500,
          label: "Evaluating and ranking results...",
          min: 65,
          max: 85,
          description: "Processing tool data and filtering by criteria",
        },
        {
          t: 6500,
          label: "Generating recommendations...",
          min: 85,
          max: maxWhilePendingBase,
          description: "Creating personalized recommendations and analysis",
        },
      ];

      const easeOutCubic = (x) => 1 - Math.pow(1 - x, 3);

      // Gradually raise the maximum cap the longer we're waiting, but never reach 100
      const dynamicCap = (elapsedMs) => {
        if (elapsedMs < 10000) return 92;
        if (elapsedMs < 18000) return 95;
        if (elapsedMs < 28000) return 97;
        return 99;
      };

      const tick = () => {
        const elapsed = Date.now() - startTime;
        // Determine current stage by elapsed thresholds
        let curr = stages[0];
        for (let i = 0; i < stages.length; i++) {
          if (elapsed <= stages[i].t) {
            curr = stages[i];
            break;
          }
          curr = stages[i];
        }
        setLoadingStage(curr.label);

        // Map elapsed within stage to progress with easing
        const prevT =
          stages.findIndex((s) => s === curr) > 0
            ? stages[stages.findIndex((s) => s === curr) - 1].t
            : 0;
        const stageSpan = Math.max(1, curr.t - prevT);
        const stageElapsed = Math.min(Math.max(elapsed - prevT, 0), stageSpan);
        const ratio = easeOutCubic(stageElapsed / stageSpan);
        const cap = dynamicCap(elapsed);
        const currIndex = stages.findIndex((s) => s === curr);
        const isLastStage = currIndex === stages.length - 1;
        // Earlier stages still honor their own max (bounded by cap),
        // but the final stage's max tracks the dynamic cap so it can go >92.
        const stageMax = isLastStage ? cap : Math.min(curr.max, cap);
        const target = Math.floor(curr.min + (stageMax - curr.min) * ratio);

        setLoadingProgress((p) => (target > p ? target : p));
      };

      tickerRef.current = window.setInterval(tick, 150); // Slightly slower updates for smoother feel

      const results = await api.searchTools(query);

      // On success: jump straight to completion
      setLoadingProgress(100);
      setLoadingStage("✅ Research complete!");

      // Cleanup and brief hold to show completion
      if (tickerRef.current) {
        clearInterval(tickerRef.current);
        tickerRef.current = null;
      }
      setTimeout(() => {
        setLoading(false);
        setLoadingProgress(0);
        setLoadingStage("");
      }, 700);

      return results;
    } catch (error) {
      if (tickerRef.current) {
        clearInterval(tickerRef.current);
        tickerRef.current = null;
      }
      setLoading(false);
      setLoadingProgress(0);
      setLoadingStage("");

      // Parse error details
      let errorDetails = null;
      try {
        errorDetails = JSON.parse(error.message);
      } catch {
        // If not JSON, treat as simple error message
        errorDetails = {
          type: "unknown",
          message: error.message || "An unexpected error occurred",
        };
      }

      setError(errorDetails);
      throw error;
    }
  };

  return {
    loading,
    loadingProgress,
    loadingStage,
    error,
    setError,
    handleSearch,
  };
};
