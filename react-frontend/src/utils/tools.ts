import type { Maintenance, Tool } from "../types";

export type PricingFilter = "all" | "free" | "freemium" | "paid";
export type SortOrder = "relevance" | "stars" | "updated" | "name";

export interface ToolFilters {
  pricing: PricingFilter;
  openSourceOnly: boolean;
  sort: SortOrder;
}

export const DEFAULT_FILTERS: ToolFilters = {
  pricing: "all",
  openSourceOnly: false,
  sort: "relevance",
};

export const MAINTENANCE_LABELS: Record<Maintenance, string> = {
  active: "Actively maintained",
  slowing: "Slowing down",
  stale: "Possibly abandoned",
  archived: "Archived",
};

function matchesPricing(tool: Tool, pricing: PricingFilter): boolean {
  switch (pricing) {
    case "free":
      return tool.pricing_model === "Free";
    case "freemium":
      return tool.pricing_model === "Freemium";
    case "paid":
      return tool.pricing_model === "Paid" || tool.pricing_model === "Enterprise";
    default:
      return true;
  }
}

export function applyFilters(tools: Tool[], filters: ToolFilters): Tool[] {
  const visible = tools.filter(
    (tool) =>
      matchesPricing(tool, filters.pricing) && (!filters.openSourceOnly || tool.is_open_source)
  );
  switch (filters.sort) {
    case "stars":
      return visible.sort((a, b) => (b.github_stars ?? -1) - (a.github_stars ?? -1));
    case "updated":
      return visible.sort((a, b) => (b.last_commit ?? "").localeCompare(a.last_commit ?? ""));
    case "name":
      return visible.sort((a, b) => a.name.localeCompare(b.name));
    default:
      return visible;
  }
}

export function formatStars(stars: number): string {
  if (stars < 1000) return String(stars);
  return `${(stars / 1000).toFixed(stars < 10_000 ? 1 : 0)}k`;
}

export function safeUrl(value?: string | null): URL | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

export function validateQuery(query: string): string | null {
  const length = query.trim().length;
  if (length < 2) return "Query must be at least 2 characters long";
  if (length > 200) return "Query must be 200 characters or fewer";
  return null;
}

const RECENT_KEY = "tool-scraper:recent-searches";
const MAX_RECENT = 5;

export function loadRecentSearches(): string[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]");
    return Array.isArray(stored) ? stored.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

export function rememberSearch(query: string): string[] {
  const text = query.trim();
  const recent = [
    text,
    ...loadRecentSearches().filter((item) => item.toLowerCase() !== text.toLowerCase()),
  ].slice(0, MAX_RECENT);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
  } catch {
    // Storage can be unavailable in private browsing. Recent searches are only a convenience.
  }
  return recent;
}
