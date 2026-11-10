import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";
import CompanyCard from "./CompanyCard";
import ResultsSection from "./ResultsSection";
import SearchSection from "./SearchSection";
import { ToastContext } from "../contexts/useToast";
import type { ResearchResult, Tool } from "../types";

const tool = (name: string, overrides: Partial<Tool> = {}): Tool => ({
  name,
  description: `${name} description`,
  website: `https://${name.toLowerCase()}.dev`,
  pricing_model: "Unknown",
  is_open_source: null,
  api_available: null,
  tech_stack: [],
  language_support: [],
  integration_capabilities: [],
  sources: [],
  ...overrides,
});

const result = (overrides: Partial<ResearchResult> = {}): ResearchResult => ({
  query: "q",
  companies: [tool("Redux", { pricing_model: "Free" }), tool("Paidly", { pricing_model: "Paid" })],
  analysis: "Pick **Redux**.",
  status: "success",
  unresearched: [],
  pricing_preference: "any",
  request_id: "1",
  processing_time: 1,
  ...overrides,
});

describe("CompanyCard", () => {
  it("hides unknown facts instead of displaying them", () => {
    render(<CompanyCard company={tool("Redux", { api_available: false })} />);
    expect(screen.queryByText(/Unknown/)).not.toBeInTheDocument();
    expect(screen.queryByText(/API/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Open Source|Proprietary/)).not.toBeInTheDocument();
  });

  it("shows GitHub facts and maintenance status", () => {
    render(
      <CompanyCard
        company={tool("Redux", {
          github_url: "https://github.com/reduxjs/redux",
          github_stars: 61000,
          license: "MIT",
          last_commit: "2026-10-01",
          maintenance: "stale",
        })}
      />
    );
    expect(screen.getByText("Possibly abandoned")).toBeInTheDocument();
    expect(screen.getByText(/★ 61k · MIT · updated 2026-10-01/)).toBeInTheDocument();
  });

  it("does not link to unsafe URLs", () => {
    render(<CompanyCard company={tool("Redux", { website: "javascript:alert(1)" })} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});

describe("ResultsSection", () => {
  it("shows tools while research is still running", () => {
    render(<ResultsSection results={null} streamedTools={[tool("Redux")]} loading />);
    expect(screen.getByText("Researching tools (1)")).toBeInTheDocument();
    expect(screen.getByText("Redux")).toBeInTheDocument();
  });

  it("renders nothing before any results exist", () => {
    const { container } = render(
      <ResultsSection results={null} streamedTools={[]} loading={false} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders model output as text, never as HTML", () => {
    const analysis = "Pick **Redux** <img src=x onerror=alert(1)>";
    const { container } = render(
      <ResultsSection results={result({ analysis })} streamedTools={[]} loading={false} />
    );
    expect(container.querySelector(".recommendation-text img")).toBeNull();
    expect(screen.getByText("Redux", { selector: "strong" })).toBeInTheDocument();
  });

  it("filters results by pricing", async () => {
    render(<ResultsSection results={result()} streamedTools={[]} loading={false} />);
    await userEvent.selectOptions(screen.getByLabelText("Pricing"), "paid");
    expect(screen.getByText("Paidly")).toBeInTheDocument();
    expect(screen.queryByText("Redux description")).not.toBeInTheDocument();
  });

  it("switches to the comparison table", async () => {
    render(<ResultsSection results={result()} streamedTools={[]} loading={false} />);
    await userEvent.click(screen.getByRole("button", { name: "Compare" }));
    const row = screen.getByRole("row", { name: /Paidly/ });
    expect(within(row).getByText("Paid")).toBeInTheDocument();
  });

  it("explains when no tools could be verified", () => {
    render(
      <ResultsSection
        results={result({ status: "no_results", companies: [] })}
        streamedTools={[]}
        loading={false}
      />
    );
    expect(screen.getByText(/couldn't find verifiable tools/)).toBeInTheDocument();
  });

  it("lists tools that could not be researched", () => {
    render(
      <ResultsSection
        results={result({ status: "partial", unresearched: ["Zustand"] })}
        streamedTools={[]}
        loading={false}
      />
    );
    expect(screen.getByText(/Couldn't verify details for: Zustand/)).toBeInTheDocument();
  });
});

describe("SearchSection", () => {
  const renderSearch = (overrides: Partial<ComponentProps<typeof SearchSection>> = {}) => {
    const props: ComponentProps<typeof SearchSection> = {
      query: "react",
      setQuery: vi.fn(),
      onSearch: vi.fn(),
      onCancel: vi.fn(),
      loading: false,
      hasResults: false,
      loadingProgress: 0,
      loadingStage: "",
      error: null,
      onError: vi.fn(),
      recentSearches: [],
      ...overrides,
    };
    render(
      <ToastContext.Provider value={vi.fn()}>
        <SearchSection {...props} />
      </ToastContext.Provider>
    );
    return props;
  };

  it("searches when an example is clicked", async () => {
    const props = renderSearch();
    await userEvent.click(screen.getByRole("button", { name: "Python web frameworks" }));
    expect(props.onSearch).toHaveBeenCalledWith("Python web frameworks");
  });

  it("accepts C++ as a query", async () => {
    const props = renderSearch({ query: "C++" });
    await userEvent.click(screen.getByRole("button", { name: /Research Topic/ }));
    expect(props.onSearch).toHaveBeenCalledWith("C++");
  });

  it("reports queries that are too short", async () => {
    const props = renderSearch({ query: "a" });
    await userEvent.click(screen.getByRole("button", { name: /Research Topic/ }));
    expect(props.onSearch).not.toHaveBeenCalled();
    expect(props.onError).toHaveBeenCalledWith(expect.objectContaining({ type: "validation" }));
  });

  it("offers Cancel with live progress while searching", async () => {
    const props = renderSearch({ loading: true, loadingProgress: 40, loadingStage: "Reading" });
    expect(screen.getByRole("status")).toHaveTextContent("Reading");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(props.onCancel).toHaveBeenCalledOnce();
  });

  it("offers a retry after a failure", async () => {
    const props = renderSearch({ error: { type: "network", message: "Connection lost" } });
    expect(screen.getByRole("alert")).toHaveTextContent("Connection lost");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(props.onSearch).toHaveBeenCalledWith("react");
  });

  it("repeats recent searches", async () => {
    const props = renderSearch({ recentSearches: ["vue tools"] });
    await userEvent.click(screen.getByRole("button", { name: "vue tools" }));
    expect(props.onSearch).toHaveBeenCalledWith("vue tools");
  });
});
