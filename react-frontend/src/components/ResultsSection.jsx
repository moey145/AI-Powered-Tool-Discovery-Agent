import React, { useEffect } from "react";
import CompanyCard from "./CompanyCard";
import "./ResultsSection.css";

const ResultsSection = ({ results }) => {
  if (!results) return null;

  // Debug logging

  // Auto-scroll to results when component mounts
  useEffect(() => {
    const scrollToResults = () => {
      const resultsSection = document.querySelector(".results-section");
      if (resultsSection) {
        const yOffset = -80; // Adjust for navbar/padding
        const y =
          resultsSection.getBoundingClientRect().top +
          window.pageYOffset +
          yOffset;
        window.scrollTo({ top: y, behavior: "smooth" });
      }
    };

    // Small delay to ensure the component is fully rendered
    const timer = setTimeout(scrollToResults, 100);
    return () => clearTimeout(timer);
  }, []); // Empty dependency array means this runs once when component mounts

  return (
    <div className="results-section">
      {/* Summary Metrics */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-icon">🏢</div>
          <div className="metric-content">
            <h3>Tools Found</h3>
            <div className="metric-value">{results.companies.length}</div>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">📖</div>
          <div className="metric-content">
            <h3>Open Source</h3>
            <div className="metric-value">
              {results.companies.filter((c) => c.is_open_source).length}
            </div>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">🔌</div>
          <div className="metric-content">
            <h3>With APIs</h3>
            <div className="metric-value">
              {results.companies.filter((c) => c.api_available).length}
            </div>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">💰</div>
          <div className="metric-content">
            <h3>Free Tools</h3>
            <div className="metric-value">
              {
                results.companies.filter((c) => c.pricing_model === "Free")
                  .length
              }
            </div>
          </div>
        </div>
      </div>

      {/* Company Cards */}
      <div className="companies-section">
        <h3>Detailed Tool Analysis ({results.companies.length} tools)</h3>
        <div className="companies-grid">
          {results.companies.map((company, index) => (
            <CompanyCard key={index} company={company} />
          ))}
        </div>
      </div>

      {/* AI Recommendations */}
      {results.analysis && (
        <div className="recommendations-section">
          <h3>AI Recommendations</h3>
          <div className="recommendations-content">
            <div
              className="recommendation-text"
              dangerouslySetInnerHTML={{
                __html: results.analysis
                  .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                  .replace(/\n/g, "<br />"),
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default ResultsSection;
