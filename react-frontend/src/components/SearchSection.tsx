import { useEffect } from "react";
import { useToast } from "../contexts/useToast";
import type { SearchError } from "../types";
import { validateQuery } from "../utils/tools";
import "./SearchSection.css";

const EXAMPLE_QUERIES = [
  "JavaScript testing frameworks",
  "Python web frameworks",
  "React state management tools",
  "Machine learning libraries",
  "Web scraping tools",
  "C++ libraries and frameworks",
];

interface SearchSectionProps {
  query: string;
  setQuery: (query: string) => void;
  onSearch: (query: string) => void;
  onCancel: () => void;
  loading: boolean;
  hasResults: boolean;
  loadingProgress: number;
  loadingStage: string;
  error: SearchError | null;
  onError: (error: SearchError | null) => void;
  recentSearches: string[];
}

const SearchSection = ({
  query,
  setQuery,
  onSearch,
  onCancel,
  loading,
  hasResults,
  loadingProgress,
  loadingStage,
  error,
  onError,
  recentSearches,
}: SearchSectionProps) => {
  const addToast = useToast();

  const submit = () => {
    const message = validateQuery(query);
    if (message) {
      onError({ type: "validation", message });
    } else {
      onSearch(query);
    }
  };

  const search = (text: string) => {
    setQuery(text);
    onSearch(text);
  };

  const handleInputChange = (value: string) => {
    setQuery(value);
    if (error) onError(null);
  };

  useEffect(() => {
    if (error?.type === "validation") {
      addToast(error.message, "warning", 6000);
    }
  }, [error, addToast]);

  const hasValidationError = error?.type === "validation";
  const hasFailure = error !== null && !hasValidationError;

  return (
    <div className={`search-section ${!hasResults ? "standalone" : ""}`}>
      <div className="search-header">
        <h1 className="app-title">Tool Scraper</h1>
        <p className="search-subtitle">
          Describe what you need and get a sourced comparison of real developer tools
        </p>
      </div>

      <div className="search-container">
        <div className={`search-input-wrapper ${hasValidationError ? "error" : ""}`}>
          <input
            type="text"
            value={query}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !loading) submit();
            }}
            placeholder="e.g., JavaScript testing frameworks, Python web frameworks..."
            className={`search-input ${hasValidationError ? "error" : ""}`}
            aria-label="Describe the tools you are looking for"
            maxLength={200}
            disabled={loading}
          />
          {hasValidationError && <div className="input-error-indicator">⚠️</div>}
        </div>

        {loading ? (
          <button onClick={onCancel} className="search-button cancel">
            Cancel
          </button>
        ) : (
          <button onClick={submit} disabled={!query.trim()} className="search-button">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
              <path d="m21 21-4.35-4.35" stroke="currentColor" strokeWidth="2" />
            </svg>
            Research Topic
          </button>
        )}
      </div>

      {loading && (
        <div className="search-progress" role="status" aria-live="polite">
          <div className="search-progress-label">
            <span>{loadingStage}</span>
            <span>{Math.round(loadingProgress)}%</span>
          </div>
          <div className="search-progress-track">
            <div className="search-progress-fill" style={{ width: `${loadingProgress}%` }} />
          </div>
        </div>
      )}

      {hasFailure && (
        <div className="search-failure" role="alert">
          <span>{error.message}</span>
          <button onClick={submit}>Try again</button>
        </div>
      )}

      {!loading && (
        <div className="example-queries">
          {EXAMPLE_QUERIES.map((example) => (
            <button key={example} className="example-query" onClick={() => search(example)}>
              {example}
            </button>
          ))}
        </div>
      )}

      {!loading && recentSearches.length > 0 && (
        <div className="recent-searches">
          <span>Recent:</span>
          {recentSearches.map((recent) => (
            <button key={recent} onClick={() => search(recent)}>
              {recent}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default SearchSection;
