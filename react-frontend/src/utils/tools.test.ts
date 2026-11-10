import { beforeEach, describe, expect, it } from "vitest";
import {
  DEFAULT_FILTERS,
  applyFilters,
  formatStars,
  loadRecentSearches,
  rememberSearch,
  safeUrl,
  validateQuery,
} from "./tools";
import type { Tool } from "../types";

const tool = (name: string, overrides: Partial<Tool> = {}): Tool => ({
  name,
  description: "",
  website: null,
  pricing_model: "Unknown",
  is_open_source: null,
  api_available: null,
  tech_stack: [],
  language_support: [],
  integration_capabilities: [],
  sources: [],
  ...overrides,
});

const free = tool("Beta", {
  pricing_model: "Free",
  is_open_source: true,
  github_stars: 10,
  last_commit: "2026-01-01",
});
const paid = tool("Alpha", {
  pricing_model: "Enterprise",
  github_stars: 500,
  last_commit: "2026-06-01",
});
const unknown = tool("Gamma");
const all = [free, paid, unknown];
const names = (tools: Tool[]) => tools.map((item) => item.name);

describe("applyFilters", () => {
  it("keeps relevance order by default", () => {
    expect(names(applyFilters(all, DEFAULT_FILTERS))).toEqual(["Beta", "Alpha", "Gamma"]);
  });

  it("treats Enterprise as paid", () => {
    expect(names(applyFilters(all, { ...DEFAULT_FILTERS, pricing: "paid" }))).toEqual(["Alpha"]);
  });

  it("filters to open source", () => {
    expect(names(applyFilters(all, { ...DEFAULT_FILTERS, openSourceOnly: true }))).toEqual([
      "Beta",
    ]);
  });

  it.each([
    ["stars", ["Alpha", "Beta", "Gamma"]],
    ["updated", ["Alpha", "Beta", "Gamma"]],
    ["name", ["Alpha", "Beta", "Gamma"]],
  ] as const)("sorts by %s with unknowns last", (sort, expected) => {
    expect(names(applyFilters(all, { ...DEFAULT_FILTERS, sort }))).toEqual(expected);
  });

  it("does not reorder the original list", () => {
    applyFilters(all, { ...DEFAULT_FILTERS, sort: "name" });
    expect(names(all)).toEqual(["Beta", "Alpha", "Gamma"]);
  });
});

describe("helpers", () => {
  it("formats star counts", () => {
    expect(formatStars(950)).toBe("950");
    expect(formatStars(1500)).toBe("1.5k");
    expect(formatStars(61000)).toBe("61k");
  });

  it("rejects unsafe URLs", () => {
    expect(safeUrl("javascript:alert(1)")).toBeNull();
    expect(safeUrl("not a url")).toBeNull();
    expect(safeUrl("https://example.com")?.hostname).toBe("example.com");
  });

  it("accepts short technical queries", () => {
    expect(validateQuery("C++")).toBeNull();
    expect(validateQuery("C#")).toBeNull();
    expect(validateQuery("a")).not.toBeNull();
  });
});

describe("recent searches", () => {
  beforeEach(() => localStorage.clear());

  it("keeps the newest first without duplicates", () => {
    rememberSearch("react");
    rememberSearch("vue");
    expect(rememberSearch("REACT")).toEqual(["REACT", "vue"]);
    expect(loadRecentSearches()).toEqual(["REACT", "vue"]);
  });

  it("limits how many are kept", () => {
    ["a1", "a2", "a3", "a4", "a5", "a6"].forEach(rememberSearch);
    expect(loadRecentSearches()).toHaveLength(5);
  });

  it("ignores corrupt storage", () => {
    localStorage.setItem("tool-scraper:recent-searches", "{oops");
    expect(loadRecentSearches()).toEqual([]);
  });
});
