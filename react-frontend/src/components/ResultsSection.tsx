import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { LuLayoutGrid, LuSearchX, LuTable } from "react-icons/lu";
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
  const sectionRef = useRef<HTMLElement>(null);
  const companies = results?.companies ?? streamedTools;
  const hasContent = results !== null || companies.length > 0;

  useEffect(() => {
    if (!hasContent) return undefined;
    const timer = setTimeout(() => {
      sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
    return () => clearTimeout(timer);
  }, [hasContent]);

  const visible = useMemo(() => applyFilters(companies, filters), [companies, filters]);

  if (!hasContent) return null;

  if (results && (results.status === "no_results" || companies.length === 0)) {
    return (
      <section className="results container" ref={sectionRef}>
        <div className="results-empty">
          <LuSearchX size={28} aria-hidden="true" />
          <h2>No verified tools found</h2>
          <p>
            We couldn't find tools we could back up with sources. Try wording the search
            differently, or try again in a moment.
          </p>
        </div>
      </section>
    );
  }

  const update = <K extends keyof ToolFilters>(key: K, value: ToolFilters[K]) =>
    setFilters((current) => ({ ...current, [key]: value }));

  const unresearched = results?.unresearched ?? [];
  const count = (test: (tool: Tool) => boolean) => companies.filter(test).length;
  const stats = [
    { label: "open source", value: count((c) => c.is_open_source === true) },
    {
      label: "free or free tier",
      value: count((c) => c.pricing_model === "Free" || c.pricing_model === "Freemium"),
    },
    { label: "actively maintained", value: count((c) => c.maintenance === "active") },
  ];

  return (
    <section className="results container" ref={sectionRef} aria-labelledby="results-heading">
      <div className="results-header">
        <div>
          <h2 id="results-heading">
            {loading ? "Researching tools" : "Results"}
            <span className="results-count">{companies.length}</span>
          </h2>
          <ul className="results-stats">
            {stats.map((stat) => (
              <li key={stat.label}>
                <strong>{stat.value}</strong> {stat.label}
              </li>
            ))}
          </ul>
        </div>

        {companies.length > 1 && (
          <div className="results-toolbar">
            <div className="segmented" role="group" aria-label="Result layout">
              <button
                className={view === "cards" ? "active" : ""}
                aria-pressed={view === "cards"}
                onClick={() => setView("cards")}
              >
                <LuLayoutGrid size={15} aria-hidden="true" />
                Cards
              </button>
              <button
                className={view === "compare" ? "active" : ""}
                aria-pressed={view === "compare"}
                onClick={() => setView("compare")}
              >
                <LuTable size={15} aria-hidden="true" />
                Compare
              </button>
            </div>
            <label className="toolbar-field">
              <span>Pricing</span>
              <select
                className="field"
                value={filters.pricing}
                onChange={(e) => update("pricing", e.target.value as PricingFilter)}
              >
                <option value="all">All</option>
                <option value="free">Free</option>
                <option value="freemium">Freemium</option>
                <option value="paid">Paid</option>
              </select>
            </label>
            <label className="toolbar-field">
              <span>Sort by</span>
              <select
                className="field"
                value={filters.sort}
                onChange={(e) => update("sort", e.target.value as SortOrder)}
              >
                <option value="relevance">Relevance</option>
                <option value="stars">GitHub stars</option>
                <option value="updated">Recently updated</option>
                <option value="name">Name</option>
              </select>
            </label>
            <label className="toolbar-check">
              <input
                type="checkbox"
                checked={filters.openSourceOnly}
                onChange={(e) => update("openSourceOnly", e.target.checked)}
              />
              Open source only
            </label>
          </div>
        )}
      </div>

      {results?.analysis && (
        <aside className="recommendation">
          <h3>Recommendation</h3>
          <p>{renderBold(results.analysis)}</p>
        </aside>
      )}

      {unresearched.length > 0 && (
        <p className="results-note">Couldn't verify details for: {unresearched.join(", ")}.</p>
      )}

      {visible.length === 0 ? (
        <p className="results-note">No tools match these filters.</p>
      ) : view === "compare" ? (
        <CompareTable tools={visible} />
      ) : (
        <div className="tool-grid">
          {visible.map((company) => (
            <CompanyCard key={company.name} company={company} />
          ))}
        </div>
      )}
    </section>
  );
};

export default ResultsSection;
