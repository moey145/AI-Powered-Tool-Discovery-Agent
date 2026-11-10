import { Fragment, useEffect, useMemo, useState } from "react";
import CompanyCard from "./CompanyCard";
import CompareTable from "./CompareTable";
import type { ResearchResult, Tool } from "../types";
import {
  DEFAULT_FILTERS,
  applyFilters,
  type PricingFilter,
  type SortOrder,
  type ToolFilters,
} from "../utils/tools";
import "./ResultsSection.css";

// Model output is built from scraped pages, so it must stay text. Only **bold** is formatted.
const renderBold = (text: string) =>
  text.split(/\*\*(.+?)\*\*/g).map((part, index) =>
    index % 2 === 1 ? (
      <strong key={index}>{part}</strong>
    ) : (
      <Fragment key={index}>{part}</Fragment>
    )
  );

interface ResultsSectionProps {
  results: ResearchResult | null;
  streamedTools: Tool[];
  loading: boolean;
}

const ResultsSection = ({ results, streamedTools, loading }: ResultsSectionProps) => {
  const [filters, setFilters] = useState<ToolFilters>(DEFAULT_FILTERS);
  const [view, setView] = useState<"cards" | "compare">("cards");
  const companies = results?.companies ?? streamedTools;
  const hasContent = results !== null || companies.length > 0;

  useEffect(() => {
    if (!hasContent) return undefined;
    const timer = setTimeout(() => {
      const section = document.querySelector(".results-section");
      if (section) {
        const y = section.getBoundingClientRect().top + window.scrollY - 80;
        window.scrollTo({ top: y, behavior: "smooth" });
      }
    }, 100);
    return () => clearTimeout(timer);
  }, [hasContent]);

  const visible = useMemo(() => applyFilters(companies, filters), [companies, filters]);

  if (!hasContent) return null;

  if (results && (results.status === "no_results" || companies.length === 0)) {
    return (
      <div className="results-section">
        <p className="results-note">
          We couldn't find verifiable tools for that search. Try different wording, or try again
          in a moment.
        </p>
      </div>
    );
  }

  const update = <K extends keyof ToolFilters>(key: K, value: ToolFilters[K]) =>
    setFilters((current) => ({ ...current, [key]: value }));

  const unresearched = results?.unresearched ?? [];

  return (
    <div className="results-section">
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-icon">🏢</div>
          <div className="metric-content">
            <h3>Tools Found</h3>
            <div className="metric-value">{companies.length}</div>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">📖</div>
          <div className="metric-content">
            <h3>Open Source</h3>
            <div className="metric-value">
              {companies.filter((c) => c.is_open_source).length}
            </div>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">💰</div>
          <div className="metric-content">
            <h3>Free or Free Tier</h3>
            <div className="metric-value">
              {
                companies.filter(
                  (c) => c.pricing_model === "Free" || c.pricing_model === "Freemium"
                ).length
              }
            </div>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">🟢</div>
          <div className="metric-content">
            <h3>Actively Maintained</h3>
            <div className="metric-value">
              {companies.filter((c) => c.maintenance === "active").length}
            </div>
          </div>
        </div>
      </div>

      <div className="companies-section">
        <h3>
          {loading ? "Researching tools" : "Detailed Tool Analysis"} ({companies.length})
        </h3>

        {companies.length > 1 && (
          <div className="results-toolbar">
            <div className="view-toggle" role="group" aria-label="Result layout">
              <button
                className={view === "cards" ? "active" : ""}
                aria-pressed={view === "cards"}
                onClick={() => setView("cards")}
              >
                Cards
              </button>
              <button
                className={view === "compare" ? "active" : ""}
                aria-pressed={view === "compare"}
                onClick={() => setView("compare")}
              >
                Compare
              </button>
            </div>
            <label>
              Pricing
              <select
                value={filters.pricing}
                onChange={(e) => update("pricing", e.target.value as PricingFilter)}
              >
                <option value="all">All</option>
                <option value="free">Free</option>
                <option value="freemium">Freemium</option>
                <option value="paid">Paid</option>
              </select>
            </label>
            <label>
              Sort by
              <select
                value={filters.sort}
                onChange={(e) => update("sort", e.target.value as SortOrder)}
              >
                <option value="relevance">Relevance</option>
                <option value="stars">GitHub stars</option>
                <option value="updated">Recently updated</option>
                <option value="name">Name</option>
              </select>
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={filters.openSourceOnly}
                onChange={(e) => update("openSourceOnly", e.target.checked)}
              />
              Open source only
            </label>
          </div>
        )}

        {unresearched.length > 0 && (
          <p className="results-note">Couldn't verify details for: {unresearched.join(", ")}.</p>
        )}

        {visible.length === 0 ? (
          <p className="results-note">No tools match these filters.</p>
        ) : view === "compare" ? (
          <CompareTable tools={visible} />
        ) : (
          <div className="companies-grid">
            {visible.map((company) => (
              <CompanyCard key={company.name} company={company} />
            ))}
          </div>
        )}
      </div>

      {results?.analysis && (
        <div className="recommendations-section">
          <h3>AI Recommendations</h3>
          <div className="recommendations-content">
            <div className="recommendation-text" style={{ whiteSpace: "pre-line" }}>
              {renderBold(results.analysis)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ResultsSection;
