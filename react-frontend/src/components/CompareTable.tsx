import type { Tool } from "../types";
import { MAINTENANCE_LABELS, formatStars, safeUrl } from "../utils/tools";

const NONE = "—";

const licensing = (tool: Tool) => {
  if (tool.license) return tool.license;
  if (tool.is_open_source === true) return "Open source";
  if (tool.is_open_source === false) return "Proprietary";
  return NONE;
};

const CompareTable = ({ tools }: { tools: Tool[] }) => (
  <div className="compare-wrapper">
    <table className="compare-table">
      <thead>
        <tr>
          <th scope="col">Tool</th>
          <th scope="col">Pricing</th>
          <th scope="col">License</th>
          <th scope="col">Stars</th>
          <th scope="col">Maintenance</th>
          <th scope="col">API</th>
          <th scope="col">Languages</th>
        </tr>
      </thead>
      <tbody>
        {tools.map((tool) => {
          const website = safeUrl(tool.website);
          return (
            <tr key={tool.name}>
              <th scope="row">
                {website ? (
                  <a href={website.href} target="_blank" rel="noopener noreferrer">
                    {tool.name}
                  </a>
                ) : (
                  tool.name
                )}
              </th>
              <td>{tool.pricing_model === "Unknown" ? NONE : tool.pricing_model}</td>
              <td>{licensing(tool)}</td>
              <td>{tool.github_stars != null ? formatStars(tool.github_stars) : NONE}</td>
              <td>{tool.maintenance ? MAINTENANCE_LABELS[tool.maintenance] : NONE}</td>
              <td>{tool.api_available ? "Yes" : NONE}</td>
              <td>{tool.language_support.slice(0, 3).join(", ") || NONE}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  </div>
);

export default CompareTable;
