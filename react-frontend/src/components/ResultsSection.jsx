import { Fragment, useEffect } from "react";
import CompanyCard from "./CompanyCard";
import "./ResultsSection.css";

// Model output is built from scraped pages, so it must stay text. Only **bold** is formatted.
const renderBold = (text) =>
  text.split(/\*\*(.+?)\*\*/g).map((part, index) =>
    index % 2 === 1 ? (
      <strong key={index}>{part}</strong>
    ) : (
      <Fragment key={index}>{part}</Fragment>
    )
  );

const ResultsSection = ({ results }) => {
  useEffect(() => {
    if (!results) return undefined;
    const timer = setTimeout(() => {
      const section = document.querySelector(".results-section");
      if (section) {
        const y = section.getBoundingClientRect().top + window.scrollY - 80;
        window.scrollTo({ top: y, behavior: "smooth" });
      }
    }, 100);
    return () => clearTimeout(timer);
  }, [results]);

  if (!results) return null;

  const { companies, analysis, status, unresearched = [] } = results;

  if (status === "no_results" || companies.length === 0) {
    return (
      <div className="results-section">
        <p className="results-note">
          We couldn't find verifiable tools for that search. Try different
          wording, or try again in a moment.
        </p>
      </div>
    );
  }

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
          <div className="metric-icon">🔌</div>
          <div className="metric-content">
            <h3>With APIs</h3>
            <div className="metric-value">
              {companies.filter((c) => c.api_available).length}
            </div>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">💰</div>
          <div className="metric-content">
            <h3>Free Tools</h3>
            <div className="metric-value">
              {companies.filter((c) => c.pricing_model === "Free").length}
            </div>
          </div>
        </div>
      </div>

      <div className="companies-section">
        <h3>Detailed Tool Analysis ({companies.length} tools)</h3>
        {unresearched.length > 0 && (
          <p className="results-note">
            Couldn't verify details for: {unresearched.join(", ")}.
          </p>
        )}
        <div className="companies-grid">
          {companies.map((company) => (
            <CompanyCard key={company.name} company={company} />
          ))}
        </div>
      </div>

      {analysis && (
        <div className="recommendations-section">
          <h3>AI Recommendations</h3>
          <div className="recommendations-content">
            <div className="recommendation-text" style={{ whiteSpace: "pre-line" }}>
              {renderBold(analysis)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ResultsSection;
