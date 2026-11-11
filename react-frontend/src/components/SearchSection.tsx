import { useEffect, useRef, useState } from "react";
import { LuCircleAlert, LuSearch, LuX } from "react-icons/lu";
import { useToast } from "../contexts/useToast";
import type { SearchError } from "../types";
import { validateQuery } from "../utils/tools";
import "./SearchSection.css";

const EXAMPLE_QUERIES = [
  "JavaScript testing frameworks",
  "Python web frameworks",
  "React state management",
  "Vector databases",
  "Web scraping tools",
  "C++ testing frameworks",
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
      addToast(error.message, "warning", 5000);
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
    <div className="hero container">
      <p className="hero-eyebrow">AI-powered tool discovery & analysis</p>
      <h1 className="hero-title">Find the Perfect Tools for Your Projects</h1>
      <p className="hero-description">
        Describe what you need. We read the web and compare real developer tools on pricing,
        licensing, and maintenance, with every source linked.
      </p>

      <form
        className={`search-box ${hasValidationError ? "invalid" : ""} ${loading ? "busy" : ""}`}
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          if (!loading) submit();
        }}
      >
        <LuSearch className="search-box-icon" size={20} aria-hidden="true" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => handleInputChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape" && query) clear();
          }}
          placeholder="e.g. Python web frameworks"
          className="search-input"
          aria-label="Describe the tools you are looking for"
          aria-invalid={hasValidationError}
          maxLength={200}
          disabled={loading}
          autoFocus={focusOnLoad}
        />
        {query && !loading ? (
          <button type="button" className="icon-button search-clear" onClick={clear} aria-label="Clear search">
            <LuX size={18} />
          </button>
        ) : (
          !loading && (
            <kbd className="search-shortcut" title="Press / to search">
              /
            </kbd>
          )
        )}
        {/* Distinct keys keep these as separate elements. If React reused one <button> and
            flipped its type to "submit" mid-click, the Cancel click would submit a new search. */}
        {loading ? (
          <button
            key="cancel"
            type="button"
            onClick={onCancel}
            className="btn btn-secondary search-submit"
          >
            Cancel
          </button>
        ) : (
          <button key="submit" type="submit" className="btn btn-primary search-submit">
            Search
          </button>
        )}
      </form>

      {loading && (
        <div className="search-progress" role="status" aria-live="polite">
          <div className="search-progress-track">
            <div className="search-progress-fill" style={{ width: `${loadingProgress}%` }} />
          </div>
          <div className="search-progress-label">
            <span>{loadingStage}</span>
            <span>{Math.round(loadingProgress)}%</span>
          </div>
        </div>
      )}

      {hasFailure && (
        <div className="search-failure" role="alert">
          <LuCircleAlert size={18} aria-hidden="true" />
          <span>{error.message}</span>
          <button type="button" className="btn btn-secondary" onClick={submit}>
            Try again
          </button>
        </div>
      )}

      {!loading && (
        <div className="suggestions">
          <span className="suggestions-label">Try</span>
          {EXAMPLE_QUERIES.map((example) => (
            <button key={example} type="button" className="chip" onClick={() => search(example)}>
              {example}
            </button>
          ))}
        </div>
      )}

      {!loading && recentSearches.length > 0 && (
        <div className="suggestions recent">
          <span className="suggestions-label">Recent</span>
          {recentSearches.map((recent) => (
            <button key={recent} type="button" className="chip chip-quiet" onClick={() => search(recent)}>
              {recent}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default SearchSection;
