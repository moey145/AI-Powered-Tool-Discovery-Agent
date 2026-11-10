export type PricingModel = "Free" | "Freemium" | "Paid" | "Enterprise" | "Unknown";
export type Maintenance = "active" | "slowing" | "stale" | "archived";

export interface Tool {
  name: string;
  description: string;
  website: string | null;
  pricing_model: PricingModel;
  is_open_source: boolean | null;
  api_available: boolean | null;
  tech_stack: string[];
  language_support: string[];
  integration_capabilities: string[];
  sources: string[];
  github_url?: string | null;
  github_stars?: number | null;
  license?: string | null;
  last_commit?: string | null;
  maintenance?: Maintenance | null;
}

export interface ResearchResult {
  query: string;
  companies: Tool[];
  analysis: string | null;
  status: "success" | "partial" | "no_results";
  unresearched: string[];
  pricing_preference: "any" | "free" | "freemium" | "paid";
  request_id: string;
  processing_time: number;
}

export interface ProgressEvent {
  type: "progress";
  stage: string;
  message: string;
  percent: number;
}

export type StreamEvent =
  | ProgressEvent
  | { type: "tool"; company: Tool }
  | { type: "result"; result: ResearchResult }
  | { type: "error"; message: string };

export type SearchErrorType = "validation" | "api" | "network";

export interface SearchError {
  type: SearchErrorType;
  message: string;
}
