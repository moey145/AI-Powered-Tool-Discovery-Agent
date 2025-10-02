import React from "react";
import "./SearchSection.css";

const SearchSection = ({
  query,
  setQuery,
  onSearch,
  loading,
  hasResults,
  loadingProgress,
  loadingStage,
  error,
  onValidationError,
}) => {
  // Client-side validation
  const validateQuery = (query) => {
    if (!query || !query.trim()) {
      return { isValid: false, message: "Query cannot be empty" };
    }

    if (query.trim().length < 2) {
      return {
        isValid: false,
        message: "Query must be at least 2 characters long",
      };
    }

    if (query.length > 200) {
      return {
        isValid: false,
        message: "Query must be less than 200 characters",
      };
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
        return {
          isValid: false,
          message: "Query contains potentially dangerous content",
        };
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
        return {
          isValid: false,
          message: "Query contains potentially dangerous SQL content",
        };
      }
    }

    // Check for excessive special characters
    const specialCharCount = (query.match(/[^\w\s]/g) || []).length;
    if (specialCharCount > query.length * 0.3) {
      return {
        isValid: false,
        message: "Query contains too many special characters",
      };
    }

    return { isValid: true };
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter") {
      const validation = validateQuery(query);
      if (validation.isValid) {
        onSearch();
      } else {
        // Show immediate toast feedback
        if (window.addToast) {
          window.addToast(validation.message, "warning", 4000);
        }
        // Also pass to parent for consistency
        if (onValidationError) {
          onValidationError({
            type: "validation",
            message: validation.message,
            errors: [{ field: "query", message: validation.message }],
          });
        }
      }
    }
  };

  const handleSearchClick = () => {
    const validation = validateQuery(query);
    if (validation.isValid) {
      onSearch();
    } else {
      // Show immediate toast feedback
      if (window.addToast) {
        window.addToast(validation.message, "warning", 4000);
      }
      // Also pass to parent for consistency
      if (onValidationError) {
        onValidationError({
          type: "validation",
          message: validation.message,
          errors: [{ field: "query", message: validation.message }],
        });
      }
    }
  };

  const handleInputChange = (e) => {
    const newQuery = e.target.value;
    setQuery(newQuery);

    // Clear error when user starts typing
    if (error && onValidationError) {
      onValidationError(null);
    }

    // Real-time validation with debounce (only for obvious errors)
    if (newQuery.length > 0) {
      const validation = validateQuery(newQuery);
      if (!validation.isValid) {
        // Only show toast for certain types of errors to avoid spam
        if (
          validation.message.includes("dangerous") ||
          validation.message.includes("SQL")
        ) {
          if (window.addToast) {
            window.addToast(validation.message, "warning", 3000);
          }
        }
      }
    }
  };

  // Show toast for any error that comes from parent (API errors, etc.)
  React.useEffect(() => {
    if (error && window.addToast) {
      const toastType = error.type === "validation" ? "warning" : "error";
      const message = error.message || "An error occurred";

      // Small delay to prevent duplicate toasts if error changes rapidly
      const timeoutId = setTimeout(() => {
        window.addToast(message, toastType, 6000);
      }, 100);

      return () => clearTimeout(timeoutId);
    }
  }, [error]);

  const exampleQueries = [
    "JavaScript testing frameworks",
    "Python web frameworks",
    "React state management tools",
    "Machine learning libraries",
    "Web scraping tools",
    "C++ libraries and frameworks",
  ];

  // Get stage icon for the button
  const getStageIcon = (stage) => {
    if (stage.includes("Initializing")) return "🚀";
    if (stage.includes("Searching") || stage.includes("Gathering")) return "🌐";
    if (stage.includes("Extracting") || stage.includes("Processing"))
      return "📄";
    if (stage.includes("Analyzing") || stage.includes("Evaluating"))
      return "🔍";
    if (stage.includes("Generating")) return "⚡";
    if (stage.includes("complete")) return "✅";
    return "🤖";
  };

  return (
    <>
      <h2 className="search-heading">Start Your Research</h2>

      <div
        className={`search-section ${!hasResults ? "standalone" : ""}`}
        id="search-section"
      >
        {/* Full-screen loading overlay */}
        {loading && (
          <div className="loading-overlay">
            <div className="loading-overlay-content">
              {/* Large horizontal loading bar with text on top */}
              <div className="loading-bar-wrapper">
                <div className="loading-text-above">{loadingStage}</div>
                <div className="loading-bar-container">
                  <div className="loading-bar-background"></div>
                  <div
                    className="loading-bar-fill"
                    style={{ width: `${loadingProgress}%` }}
                  ></div>
                  <div className="loading-bar-text">
                    {Math.round(loadingProgress)}%
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="search-header">
          <h1 className="app-title">Tool Scraper</h1>
          <p className="search-subtitle">
            Simply describe what you're looking for and we'll find the best
            tools for you
          </p>
        </div>

        <div className="search-container">
          <div
            className={`search-input-wrapper ${
              error && error.type === "validation" ? "error" : ""
            }`}
          >
            <input
              type="text"
              value={query}
              onChange={handleInputChange}
              placeholder="e.g., JavaScript testing frameworks, Python web frameworks, React state management tools..."
              className={`search-input ${
                error && error.type === "validation" ? "error" : ""
              }`}
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
            {error && error.type === "validation" && (
              <div className="input-error-indicator">⚠️</div>
            )}
          </div>

          <button
            onClick={handleSearchClick}
            disabled={loading || !query.trim()}
            className="search-button"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <circle
                cx="11"
                cy="11"
                r="8"
                stroke="currentColor"
                strokeWidth="2"
              />
              <path
                d="m21 21-4.35-4.35"
                stroke="currentColor"
                strokeWidth="2"
              />
            </svg>
            Research Topic
          </button>
        </div>

        <div className="example-queries">
          {exampleQueries.map((example, index) => (
            <button
              key={index}
              className="example-query"
              onClick={() => setQuery(example)}
              disabled={loading}
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </>
  );
};

export default SearchSection;
