import { useEffect } from "react";
import "./SearchSection.css";

const EXAMPLE_QUERIES = [
  "JavaScript testing frameworks",
  "Python web frameworks",
  "React state management tools",
  "Machine learning libraries",
  "Web scraping tools",
  "C++ libraries and frameworks",
];

const validateQuery = (query) => {
  const length = query.trim().length;
  if (length < 2) return "Query must be at least 2 characters long";
  if (length > 200) return "Query must be 200 characters or fewer";
  return null;
};

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
  const submit = () => {
    const message = validateQuery(query);
    if (message) {
      onValidationError({ type: "validation", message });
    } else {
      onSearch();
    }
  };

  const handleInputChange = (e) => {
    setQuery(e.target.value);
    if (error) onValidationError(null);
  };

  useEffect(() => {
    if (error && window.addToast) {
      window.addToast(
        error.message || "An error occurred",
        error.type === "validation" ? "warning" : "error",
        6000
      );
    }
  }, [error]);

  const hasValidationError = error?.type === "validation";

  return (
    <>
      <h2 className="search-heading">Start Your Research</h2>

      <div
        className={`search-section ${!hasResults ? "standalone" : ""}`}
        id="search-section"
      >
        {loading && (
          <div className="loading-overlay" role="status" aria-live="polite">
            <div className="loading-overlay-content">
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
          <div className={`search-input-wrapper ${hasValidationError ? "error" : ""}`}>
            <input
              type="text"
              value={query}
              onChange={handleInputChange}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder="e.g., JavaScript testing frameworks, Python web frameworks, React state management tools..."
              className={`search-input ${hasValidationError ? "error" : ""}`}
              aria-label="Describe the tools you are looking for"
              maxLength={200}
              disabled={loading}
            />
            {hasValidationError && <div className="input-error-indicator">⚠️</div>}
          </div>

          <button
            onClick={submit}
            disabled={loading || !query.trim()}
            className="search-button"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
              <path d="m21 21-4.35-4.35" stroke="currentColor" strokeWidth="2" />
            </svg>
            Research Topic
          </button>
        </div>

        <div className="example-queries">
          {EXAMPLE_QUERIES.map((example) => (
            <button
              key={example}
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
