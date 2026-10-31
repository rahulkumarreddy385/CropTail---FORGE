from ai import llm


def test_gemini_request_and_function_response(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
    requests = []
    responses = [
        {"candidates": [{"content": {"parts": [
            {"functionCall": {"name": "lookup", "args": {"count": 2}, "id": "call-1"}},
        ]}}]},
        {"candidates": [{"content": {"parts": [{"text": "Found two records."}]}}]},
    ]

    class Response:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    def fake_post(url, **kwargs):
        requests.append((url, kwargs))
        return Response(responses.pop(0))

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    tool = {
        "name": "lookup",
        "description": "Look up records.",
        "input_schema": {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": ["count"],
            "additionalProperties": False,
        },
    }
    initial = llm.messages("Use tools.", [{
        "role": "user",
        "content": [
            {"type": "image", "source": {"media_type": "image/jpeg", "data": "aGVsbG8="}},
            {"type": "text", "text": "Find two records."},
        ],
    }], tools=[tool])

    assert initial["content"] == [{
        "type": "tool_use", "id": "call-1", "name": "lookup", "input": {"count": 2},
    }]
    url, request = requests[0]
    assert url.endswith("/models/gemini-2.5-flash:generateContent")
    assert request["headers"]["x-goog-api-key"] == "test-key"
    assert request["json"]["systemInstruction"]["parts"][0]["text"] == "Use tools."
    assert request["json"]["contents"][0]["parts"][0]["inlineData"] == {
        "mimeType": "image/jpeg", "data": "aGVsbG8=",
    }
    declaration = request["json"]["tools"][0]["functionDeclarations"][0]
    assert declaration["parameters"] == {
        "type": "OBJECT",
        "properties": {"count": {"type": "INTEGER"}},
        "required": ["count"],
    }

    final = llm.messages("Use tools.", [
        {"role": "user", "content": "Find two records."},
        {"role": "assistant", "content": initial["content"]},
        {"role": "user", "content": [{
            "type": "tool_result", "tool_use_id": "call-1", "content": "Two records.",
        }]},
    ])
    assert final["content"] == [{"type": "text", "text": "Found two records."}]
    history = requests[1][1]["json"]["contents"]
    assert history[1]["parts"][0]["functionCall"]["id"] == "call-1"
    assert history[2]["parts"][0]["functionResponse"] == {
        "name": "lookup", "id": "call-1", "response": {"result": "Two records."},
    }
