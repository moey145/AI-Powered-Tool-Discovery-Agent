import json

import pytest
from fastapi.testclient import TestClient

from api import create_app
from src.models import CompanyInfo, ResearchResult


class FakeWorkflow:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.result = ResearchResult(
            query="react", companies=[CompanyInfo(name="Redux", description="State")]
        )

    async def run(self, query):
        if self.error:
            raise self.error
        return self.result

    async def stream(self, query):
        yield {"type": "progress", "stage": "searching", "message": "Searching", "percent": 5}
        if self.error:
            raise self.error
        yield {"type": "result", "result": self.result}


def client_for(settings, workflow=None) -> TestClient:
    workflow = workflow or FakeWorkflow()
    return TestClient(
        create_app(settings, workflow_factory=lambda _settings, _client: workflow),
        raise_server_exceptions=False,
    )


def parse_sse(text: str) -> list[dict]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in text.splitlines()
        if line.startswith("data: ")
    ]


def test_health_exposes_no_configuration(settings):
    with client_for(settings) as client:
        body = client.get("/health").json()
    assert set(body) == {"status", "version"}


def test_research_returns_results_with_request_metadata(settings):
    with client_for(settings) as client:
        body = client.post("/research", json={"query": "react"}).json()
    assert body["companies"][0]["name"] == "Redux"
    assert body["request_id"]
    assert body["processing_time"] >= 0


@pytest.mark.parametrize(
    "query", ["C++", "C#", ".NET", "CI/CD", "tools to insert into tables", "O'Reilly tools"]
)
def test_accepts_legitimate_technical_queries(settings, query):
    with client_for(settings) as client:
        assert client.post("/research", json={"query": query}).status_code == 200


@pytest.mark.parametrize("query", ["", " ", "a", "x" * 201, "\x00\x01"])
def test_rejects_invalid_queries(settings, query):
    with client_for(settings) as client:
        assert client.post("/research", json={"query": query}).status_code == 422


def test_rate_limit_returns_429_with_retry_after(settings):
    settings.rate_limit_per_minute = 1
    with client_for(settings) as client:
        assert client.post("/research", json={"query": "react"}).status_code == 200
        response = client.post("/research", json={"query": "react"})
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_rate_limit_uses_the_last_forwarded_address(settings):
    settings.rate_limit_per_minute = 1
    with client_for(settings) as client:
        first = {"X-Forwarded-For": "1.1.1.1, 9.9.9.9"}
        spoofed = {"X-Forwarded-For": "2.2.2.2, 9.9.9.9"}
        assert client.post("/research", json={"query": "ab"}, headers=first).status_code == 200
        assert client.post("/research", json={"query": "ab"}, headers=spoofed).status_code == 429


def test_errors_do_not_leak_internal_details(settings):
    workflow = FakeWorkflow(RuntimeError("secret internal detail"))
    with client_for(settings, workflow) as client:
        response = client.post("/research", json={"query": "react"})
    assert response.status_code == 500
    assert "secret" not in response.text


def test_stream_emits_progress_then_result(settings):
    with client_for(settings) as client:
        response = client.post("/research/stream", json={"query": "react"})
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert [event["type"] for event in events] == ["progress", "result"]
    assert events[-1]["result"]["companies"][0]["name"] == "Redux"
    assert events[-1]["result"]["request_id"]


def test_stream_errors_are_generic(settings):
    workflow = FakeWorkflow(RuntimeError("secret internal detail"))
    with client_for(settings, workflow) as client:
        response = client.post("/research/stream", json={"query": "react"})
    events = parse_sse(response.text)
    assert events[-1]["type"] == "error"
    assert "secret" not in response.text


def test_cors_allows_only_configured_origins(settings):
    settings.allowed_origins = "https://app.example.com"
    with client_for(settings) as client:
        allowed = client.get("/health", headers={"Origin": "https://app.example.com"})
        denied = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert allowed.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "access-control-allow-origin" not in denied.headers
