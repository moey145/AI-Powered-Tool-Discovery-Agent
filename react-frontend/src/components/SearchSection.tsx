import { useEffect, useRef, useState } from "react";
import { useToast } from "../contexts/useToast";
import type { SearchError } from "../types";
import { validateQuery } from "../utils/tools";
import "./SearchSection.css";

const EXAMPLE_QUERIES = [
  "JavaScript testing frameworks",
  "Python web frameworks",
  "React state management tools",
  "Vector databases",
  "Web scraping tools",
  "C++ libraries and frameworks",
];

const isTyping = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

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
  const inputRef = useRef<HTMLInputElement>(null);
  // Focus the box on desktop only: on phones it would pop the keyboard over the page.
  const [focusOnLoad] = useState(
    () =>
      Boolean(window.matchMedia?.("(pointer: fine)").matches) &&
      !new URLSearchParams(window.location.search).get("q")
  );

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey && !isTyping(e.target)) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (error?.type === "validation") {
      addToast(error.message, "warning", 6000);
    }
  }, [error, addToast]);

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

  const clear = () => {
    handleInputChange("");
    inputRef.current?.focus();
  };

  const hasValidationError = error?.type === "validation";
  const hasFailure = error !== null && !hasValidationError;

  return (
    <div className="search-hero">
      <div className="hero-badge">
        <span className="badge-icon" aria-hidden="true">
          🔍
        </span>
        <span className="badge-text">AI-Powered Tool Discovery & Analysis</span>
      </div>

      <h1 className="hero-title">
        Find the Perfect <span className="hero-gradient-text">Tools</span> for Your Projects
      </h1>

      <p className="hero-description">
        Describe what you need and get a sourced comparison of real developer tools, with pricing,
        licenses, and maintenance status.
      </p>

      <div className={`search-section ${!hasResults ? "standalone" : ""}`}>
        <div className="search-container">
          <div className={`search-input-wrapper ${hasValidationError ? "error" : ""}`}>
            <svg
              className="search-input-icon"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
              <path d="m21 21-4.35-4.35" stroke="currentColor" strokeWidth="2" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => handleInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !loading) submit();
                if (e.key === "Escape" && query) clear();
              }}
              placeholder="Describe the tools you need..."
              className={`search-input ${hasValidationError ? "error" : ""}`}
              aria-label="Describe the tools you are looking for"
              maxLength={200}
              disabled={loading}
              autoFocus={focusOnLoad}
            />
            {query && !loading ? (
              <button className="search-clear" onClick={clear} aria-label="Clear search">
                ×
              </button>
            ) : (
              !loading && (
                <kbd className="search-shortcut" title="Press / to search">
                  /
                </kbd>
              )
            )}
          </div>

          {loading ? (
            <button onClick={onCancel} className="search-button cancel">
              Cancel
            </button>
          ) : (
            <button onClick={submit} disabled={!query.trim()} className="search-button">
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
            <span className="example-label">Try:</span>
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
    </div>
  );
};

export default SearchSection;
