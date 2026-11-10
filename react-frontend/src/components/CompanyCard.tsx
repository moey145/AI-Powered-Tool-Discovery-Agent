import type { Tool } from "../types";
import { MAINTENANCE_LABELS, formatStars, safeUrl } from "../utils/tools";
import "./CompanyCard.css";

const TagList = ({ title, items, limit }: { title: string; items: string[]; limit: number }) =>
  items.length > 0 ? (
    <div className="detail-section">
      <h5>{title}</h5>
      <div className="tags">
        {items.slice(0, limit).map((item) => (
          <span key={item} className="tag">
            {item}
          </span>
        ))}
        {items.length > limit && <span className="tag more">+{items.length - limit} more</span>}
      </div>
    </div>
  ) : null;

const CompanyCard = ({ company }: { company: Tool }) => {
  const website = safeUrl(company.website);
  const repository = safeUrl(company.github_url);
  const sources = company.sources.map(safeUrl).filter((url): url is URL => url !== null);

  return (
    <div className="company-card">
      <div className="company-header">
        <h4>{company.name}</h4>
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

      <p className="company-description">{company.description}</p>

      <div className="company-metrics">
        {company.pricing_model !== "Unknown" && (
          <span className="metric-badge pricing">💰 {company.pricing_model}</span>
        )}
        {company.is_open_source != null && (
          <span className={`metric-badge ${company.is_open_source ? "open-source" : "proprietary"}`}>
            {company.is_open_source ? "📖 Open Source" : "🔒 Proprietary"}
          </span>
        )}
        {company.api_available && <span className="metric-badge api-yes">🔌 API</span>}
        {company.maintenance && (
          <span className={`metric-badge maintenance-${company.maintenance}`}>
            {MAINTENANCE_LABELS[company.maintenance]}
          </span>
        )}
      </div>

      {repository && (
        <p className="repo-facts">
          <a href={repository.href} target="_blank" rel="noopener noreferrer">
            GitHub
          </a>
          {company.github_stars != null && ` · ★ ${formatStars(company.github_stars)}`}
          {company.license && ` · ${company.license}`}
          {company.last_commit && ` · updated ${company.last_commit}`}
        </p>
      )}

      <div className="company-details">
        <TagList title="🛠️ Tech Stack" items={company.tech_stack} limit={5} />
        <TagList title="💻 Languages" items={company.language_support} limit={5} />
        <TagList title="🔗 Integrations" items={company.integration_capabilities} limit={4} />

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
