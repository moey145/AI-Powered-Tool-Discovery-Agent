import { Fragment, type ReactNode } from "react";
import { LuArrowUpRight, LuGithub, LuStar } from "react-icons/lu";
import type { Maintenance, Tool } from "../types";
import { MAINTENANCE_LABELS, formatStars, safeUrl } from "../utils/tools";
import "./CompanyCard.css";

const hostname = (url: URL) => url.hostname.replace(/^www\./, "");

// Short enough to keep the summary on one line; the full wording shows on hover.
const SHORT_STATUS: Record<Maintenance, string> = {
  active: "Active",
  slowing: "Slowing",
  stale: "Inactive",
  archived: "Archived",
};

/** One link per site: several pages from the same site read as clutter. */
const uniqueSites = (urls: URL[]) => {
  const seen = new Set<string>();
  return urls.filter((url) => !seen.has(hostname(url)) && seen.add(hostname(url)));
};

const Detail = ({ label, children }: { label: string; children: ReactNode }) => (
  <div className="tool-detail">
    <dt>{label}</dt>
    <dd>{children}</dd>
  </div>
);

const CompanyCard = ({ company }: { company: Tool }) => {
  const website = safeUrl(company.website);
  const repository = safeUrl(company.github_url);
  const sources = uniqueSites(
    company.sources.map(safeUrl).filter((url): url is URL => url !== null)
  );

  const facts: { key: string; node: ReactNode }[] = [];
  // A license like MIT already says "open source", so show it instead of the generic label.
  if (company.license) {
    facts.push({
      key: "license",
      node: <span title={`${company.license} license`}>{company.license}</span>,
    });
  } else if (company.is_open_source != null) {
    facts.push({ key: "oss", node: company.is_open_source ? "Open source" : "Proprietary" });
  }
  if (company.github_stars != null) {
    facts.push({
      key: "stars",
      node: (
        <span className="tool-stars">
          <LuStar size={12} aria-hidden="true" />
          {formatStars(company.github_stars)}
        </span>
      ),
    });
  }
  if (company.maintenance) {
    facts.push({
      key: "status",
      node: (
        <span
          className={`tool-status status-${company.maintenance}`}
          title={MAINTENANCE_LABELS[company.maintenance]}
        >
          <span className="status-dot" aria-hidden="true" />
          {SHORT_STATUS[company.maintenance]}
        </span>
      ),
    });
  }

  const details: { label: string; value: ReactNode }[] = [];
  if (company.language_support.length) {
    details.push({ label: "Languages", value: company.language_support.slice(0, 5).join(", ") });
  }
  if (company.integration_capabilities.length) {
    details.push({
      label: "Integrations",
      value: company.integration_capabilities.slice(0, 5).join(", "),
    });
  }
  if (company.tech_stack.length) {
    details.push({ label: "Built with", value: company.tech_stack.slice(0, 5).join(", ") });
  }
  if (company.api_available) details.push({ label: "API", value: "Available" });
  if (company.last_commit) details.push({ label: "Last updated", value: company.last_commit });
  if (sources.length) {
    details.push({
      label: "Sources",
      value: sources.map((source, index) => (
        <Fragment key={source.href}>
          {index > 0 && ", "}
          <a href={source.href} target="_blank" rel="noopener noreferrer">
            {hostname(source)}
          </a>
        </Fragment>
      )),
    });
  }

  return (
    <article className="tool-card">
      <header className="tool-card-header">
        <h3>{company.name}</h3>
        <div className="tool-card-links">
          {website && (
            <a
              href={website.href}
              target="_blank"
              rel="noopener noreferrer"
              className="tool-card-site"
              aria-label={`${company.name} website`}
            >
              {hostname(website)}
              <LuArrowUpRight size={14} aria-hidden="true" />
            </a>
          )}
          {repository && (
            <a
              href={repository.href}
              target="_blank"
              rel="noopener noreferrer"
              className="tool-card-repo"
              aria-label={`${company.name} on GitHub`}
              title="GitHub repository"
            >
              <LuGithub size={16} aria-hidden="true" />
            </a>
          )}
        </div>
      </header>

      <p className="tool-card-description">{company.description}</p>

      {(company.pricing_model !== "Unknown" || facts.length > 0) && (
        <div className="tool-summary">
          {company.pricing_model !== "Unknown" && (
            <span className={`badge ${company.pricing_model === "Free" ? "badge-positive" : ""}`}>
              {company.pricing_model}
            </span>
          )}
          {facts.map((fact) => (
            <span key={fact.key} className="tool-summary-fact">
              {fact.node}
            </span>
          ))}
        </div>
      )}

      {details.length > 0 && (
        <dl className="tool-details">
          {details.map((detail) => (
            <Detail key={detail.label} label={detail.label}>
              {detail.value}
            </Detail>
          ))}
        </dl>
      )}
    </article>
  );
};

export default CompanyCard;
