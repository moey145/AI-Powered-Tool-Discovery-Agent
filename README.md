# Tool Scraper

Describe the developer tool you need in plain English. Tool Scraper searches the web, reads what it finds, and returns a comparison of real tools with pricing, licensing, and the sources behind each result.

It only reports what it can trace to a page it retrieved. A tool that isn't named in the sources is dropped, and a fact the sources don't state stays "Unknown".

## How it works

A [LangGraph](https://langchain-ai.github.io/langgraph/) pipeline runs three steps and streams its real progress to the browser:

1. **Discover:** search the web, read the top comparison articles, and have the LLM pick the relevant tools and work out any pricing preference. Names that don't appear in the source text are rejected.
2. **Research:** for each tool, read its own pages and pricing page, extract facts into a validated schema, then add license, stars, and maintenance data from the GitHub API. Each tool appears in the browser as soon as it finishes, and a timeout keeps the ones already done.
3. **Recommend:** write a short recommendation from those facts.

## Project layout

```
advanced-agent/          FastAPI backend and research pipeline
  api.py                 HTTP API with streaming, rate limits, and CORS
  main.py                Command-line interface
  src/workflow.py        The pipeline
  src/search_providers.py  Brave, Google, and DuckDuckGo search
  src/scraper.py         Page fetching and text extraction
  src/github.py          Verified repository facts
  src/net.py             HTTP client that blocks private addresses
  src/store.py           Result cache, in memory or Redis
  tests/                 Offline test suite
  evals/                 Live quality benchmark
  guides/                Static guide page generator
react-frontend/          React, TypeScript, and Vite web app
Dockerfile               Backend container image
```

## Getting started

You need Python 3.13, [uv](https://docs.astral.sh/uv/), Node.js 22, and an OpenAI API key.

**Backend**

```bash
cd advanced-agent
uv sync
cp .env.example .env      # then add your keys
uv run uvicorn api:app --reload --port 8000
```

**Frontend**

```bash
cd react-frontend
npm install
npm run dev               # http://localhost:5173
```

The frontend calls `http://localhost:8000` unless `VITE_API_BASE_URL` is set.

## Configuration

Set these as environment variables or in `advanced-agent/.env`. Only `OPENAI_API_KEY` is required.

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | none | OpenAI API key |
| `OPENAI_MODEL` | `gpt-6-luna` | Model for all LLM steps |
| `BRAVE_SEARCH_API_KEY` | none | Recommended search provider |
| `GOOGLE_CUSTOM_SEARCH_API_KEY`, `GOOGLE_SEARCH_ENGINE_ID` | none | Google search, which Google discontinues on 2027-01-01 |
| `GITHUB_TOKEN` | none | Raises GitHub's API limit so license, star, and maintenance data stays complete. It needs no permissions |
| `REDIS_URL` | none | Shares the cache and rate limits across server instances |
| `SEARCH_PROVIDER` | `auto` | Provider to try first: `auto`, `brave`, `google_custom_search`, or `duckduckgo` |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated browser origins allowed to call the API |
| `RATE_LIMIT_PER_MINUTE` | `5` | Searches per client per minute |
| `DAILY_SEARCH_BUDGET` | `200` | Total searches per day |

With no search key, the agent falls back to DuckDuckGo's HTML page, which is rate-limited and less reliable. Without `REDIS_URL`, the cache and rate limits are held in memory and apply to each server instance separately.

Each search logs its token counts and estimated cost.

## API

| Endpoint | Description |
|---|---|
| `POST /research/stream` | Runs a search and streams `progress` and `tool` events, then a `result` or `error` event |
| `POST /research` | Runs a search and returns the final JSON |
| `GET /examples` | Example queries |
| `GET /health` | Health check |

Both search endpoints take `{"query": "Python web frameworks"}`. The result's `status` is `success`, `partial` (some tools are listed in `unresearched`), or `no_results`.

## Testing

```bash
# Backend, offline
cd advanced-agent && uv run pytest && uv run ruff check .

# Frontend
cd react-frontend && npm test && npm run lint

# Quality benchmark: uses live APIs and spends credits
cd advanced-agent && uv run python -m evals.run

# Regenerate the static guide pages: uses live APIs and spends credits
cd advanced-agent && uv run python -m guides.generate
```

## Deployment

Build the backend image from the repository root and pass secrets at runtime:

```bash
docker build -t tool-scraper .
docker run -p 8080:8080 --env-file advanced-agent/.env tool-scraper
```

In production, set `ALLOWED_ORIGINS` to your frontend's URL or the browser will block its requests. Set `VITE_API_BASE_URL` on the frontend to your backend's URL.

### Automatic backend deploys

The `deploy-backend` CI job deploys to Cloud Run after every passing push to `main`. It stays skipped until you complete this one-time setup:

1. In Google Secret Manager, create the secrets `openai-api-key`, `brave-search-api-key`, and `github-token`, and let the Cloud Run service account read them.
2. Create a service account for deploys with the Cloud Run Admin, Cloud Build Editor, Artifact Registry Writer, Storage Admin, and Service Account User roles.
3. Set up [Workload Identity Federation](https://github.com/google-github-actions/auth#workload-identity-federation-through-a-service-account) so this repository can use that service account, with no long-lived key.
4. Add the GitHub repository variables `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_DEPLOY_SERVICE_ACCOUNT`.

Vercel deploys the frontend separately and may finish first, so keep API changes backward compatible.

## License

MIT. See [LICENSE](LICENSE).
