# Tool Scraper

Describe the developer tool you need in plain English. Tool Scraper searches the web, reads what it finds, and returns a comparison of real tools with pricing, licensing, and the sources behind each result.

It only reports what it can trace to a page it retrieved. A tool that isn't named in the sources is dropped, and a fact the sources don't state stays "Unknown".

## How it works

A [LangGraph](https://langchain-ai.github.io/langgraph/) pipeline runs three steps and streams its real progress to the browser:

1. **Discover:** search the web, read the top comparison articles, and have the LLM pick the relevant tools and work out any pricing preference. Names that don't appear in the source text are rejected.
2. **Research:** for each tool, find and read its own pages, then extract facts into a validated schema. If some tools run out of time, the ones that finished are still returned.
3. **Recommend:** write a short recommendation from those facts.

## Project layout

```
advanced-agent/          FastAPI backend and research pipeline
  api.py                 HTTP API with streaming, rate limits, and CORS
  main.py                Command-line interface
  src/workflow.py        The pipeline
  src/search_providers.py  Brave, Google, and DuckDuckGo search
  src/scraper.py         Page fetching and text extraction
  src/net.py             HTTP client that blocks private addresses
  tests/                 Offline test suite
  evals/                 Live quality benchmark
react-frontend/          React and Vite web app
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
| `SEARCH_PROVIDER` | `auto` | Provider to try first: `auto`, `brave`, `google_custom_search`, or `duckduckgo` |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated browser origins allowed to call the API |
| `RATE_LIMIT_PER_MINUTE` | `5` | Searches per client per minute |
| `DAILY_SEARCH_BUDGET` | `200` | Total searches per day |

With no search key, the agent falls back to DuckDuckGo's HTML page, which is rate-limited and less reliable. Rate limits are held in memory, so they apply to each server instance separately.

## API

| Endpoint | Description |
|---|---|
| `POST /research/stream` | Runs a search and streams `progress` events, then a `result` or `error` event |
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
```

## Deployment

Build the backend image from the repository root and pass secrets at runtime:

```bash
docker build -t tool-scraper .
docker run -p 8080:8080 --env-file advanced-agent/.env tool-scraper
```

In production, set `ALLOWED_ORIGINS` to your frontend's URL or the browser will block its requests. Set `VITE_API_BASE_URL` on the frontend to your backend's URL.

## License

MIT. See [LICENSE](LICENSE).
