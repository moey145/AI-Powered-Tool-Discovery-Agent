import React from "react";
import "./CompanyCard.css";

const safeUrl = (value) => {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url : null;
  } catch {
    return null;
  }
};

const CompanyCard = ({ company }) => {
  const website = safeUrl(company.website);
  const sources = (company.sources || []).map(safeUrl).filter(Boolean);

  return (
    <div className="company-card">
      <div className="company-header">
        <h4>{company.name || "Unknown Tool"}</h4>
        {website && (
          <a
            href={website.href}
            target="_blank"
            rel="noopener noreferrer"
            className="website-link"
          >
            🌐 Visit ↗
          </a>
        )}
      </div>

      <p className="company-description">
        {company.description || "No description available"}
      </p>

      <div className="company-metrics">
        <span className="metric-badge pricing">
          💰 {company.pricing_model || "Unknown"}
        </span>

        {company.is_open_source != null && (
          <span
            className={`metric-badge ${
              company.is_open_source ? "open-source" : "proprietary"
            }`}
          >
            {company.is_open_source ? "📖 Open Source" : "🔒 Proprietary"}
          </span>
        )}

        {company.api_available != null && (
          <span
            className={`metric-badge ${
              company.api_available ? "api-yes" : "api-no"
            }`}
          >
            🔌 {company.api_available ? "API Available" : "No API"}
          </span>
        )}
      </div>

      <div className="company-details">
        {company.tech_stack && company.tech_stack.length > 0 && (
          <div className="detail-section">
            <h5>🛠️ Tech Stack</h5>
            <div className="tags">
              {company.tech_stack.slice(0, 5).map((tech, i) => (
                <span key={i} className="tag">
                  {tech}
                </span>
              ))}
              {company.tech_stack.length > 5 && (
                <span className="tag more">
                  +{company.tech_stack.length - 5} more
                </span>
              )}
            </div>
          </div>
        )}

        {company.language_support && company.language_support.length > 0 && (
          <div className="detail-section">
            <h5>💻 Languages</h5>
            <div className="tags">
              {company.language_support.slice(0, 5).map((lang, i) => (
                <span key={i} className="tag">
                  {lang}
                </span>
              ))}
            </div>
          </div>
        )}

        {company.integration_capabilities &&
          company.integration_capabilities.length > 0 && (
            <div className="detail-section">
              <h5>🔗 Integrations</h5>
              <div className="tags">
                {company.integration_capabilities
                  .slice(0, 4)
                  .map((integration, i) => (
                    <span key={i} className="tag">
                      {integration}
                    </span>
                  ))}
              </div>
            </div>
          )}

        {sources.length > 0 && (
          <div className="detail-section">
            <h5>📚 Sources</h5>
            <div className="tags">
              {sources.map((source) => (
                <a
                  key={source.href}
                  href={source.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="tag"
                >
                  {source.hostname.replace(/^www\./, "")}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CompanyCard;
