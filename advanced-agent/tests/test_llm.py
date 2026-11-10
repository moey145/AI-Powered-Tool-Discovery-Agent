"""Exercise the real LangChain client against a simulated OpenAI endpoint."""

import json

import httpx

from src.models import PricingModel, ToolAnalysis, ToolDiscovery
from src.workflow import OpenAILLM


def completion(content: str) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def assert_strict(schema: dict) -> None:
    """Apply OpenAI's strict-mode rules to every object in a JSON schema."""
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == set(schema["properties"])
        assert "default" not in schema
        for value in schema.values():
            assert_strict(value)
    elif isinstance(schema, list):
        for item in schema:
            assert_strict(item)


def llm_returning(settings, content: str, requests: list[httpx.Request]) -> OpenAILLM:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=completion(content))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAILLM(settings, http_client=client)


async def test_structured_discovery_parses_and_sends_a_strict_schema(settings):
    requests: list[httpx.Request] = []
    content = json.dumps({"tools": ["Redux"], "pricing_preference": "free"})
    result = await llm_returning(settings, content, requests).structured(
        ToolDiscovery, "system", "user"
    )
    assert result == ToolDiscovery(tools=["Redux"], pricing_preference="free")
    assert requests[0].url.path.endswith("/chat/completions")
    body = json.loads(requests[0].content)
    assert body["model"] == settings.openai_model
    assert body["response_format"]["json_schema"]["strict"] is True
    assert_strict(body["response_format"]["json_schema"]["schema"])


async def test_structured_analysis_schema_is_strict_and_parses_enums(settings):
    requests: list[httpx.Request] = []
    content = json.dumps(
        {
            "describes_requested_tool": True,
            "relevant_sources": ["https://a.dev"],
            "description": "A tool.",
            "website": None,
            "pricing_model": "Freemium",
            "is_open_source": None,
            "api_available": True,
            "tech_stack": [],
            "language_support": ["Python"],
            "integration_capabilities": [],
        }
    )
    result = await llm_returning(settings, content, requests).structured(
        ToolAnalysis, "system", "user"
    )
    assert result.pricing_model is PricingModel.FREEMIUM
    assert result.is_open_source is None
    assert_strict(json.loads(requests[0].content)["response_format"]["json_schema"]["schema"])


async def test_text_returns_message_content(settings):
    requests: list[httpx.Request] = []
    assert await llm_returning(settings, "Pick Redux.", requests).text("s", "u") == "Pick Redux."
