import io
import json
import urllib.error
from pathlib import Path

from targetcheck.providers.ollama_cloud import OllamaCloudClient, load_api_keys


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps(self.payload).encode()


def test_rotates_after_quota_error_without_exposing_keys():
    calls = []

    def opener(request, timeout):
        calls.append(request.headers["Authorization"])
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 429, "quota", {}, io.BytesIO())
        return FakeResponse({"message": {"content": "ok"}})

    client = OllamaCloudClient(("secret-one", "secret-two"), opener=opener)
    response = client.chat("gpt-oss:20b", [{"role": "user", "content": "hi"}])
    assert response["message"]["content"] == "ok"
    assert [attempt.category for attempt in client.last_attempts] == ["rotate", "success"]
    assert "secret" not in repr(client.last_attempts)


def test_loads_labelled_key_lines(tmp_path: Path):
    path = tmp_path / "keys.txt"
    path.write_text("account one key-one\nOLLAMA_API_KEY=key-two\n")
    assert load_api_keys(path) == ("key-one", "key-two")
