from __future__ import annotations

import io
import json
import unittest

from Son.vastai.run_local import OllamaLocalClient, model_names, parse_think, safe_model_name


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


class LocalClientTests(unittest.TestCase):
    def test_chat_uses_local_no_auth_payload(self) -> None:
        captured = {}

        def opener(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse({"message": {"content": "OK"}})

        client = OllamaLocalClient(num_ctx=4096, opener=opener)
        result = client.chat(
            "qwen3:8b",
            [{"role": "user", "content": "hello"}],
            format_schema={"type": "object"},
            options={"temperature": 0.0},
            think=False,
        )
        request = captured["request"]
        payload = json.loads(request.data)
        self.assertEqual(result["message"]["content"], "OK")
        self.assertEqual(payload["options"]["num_ctx"], 4096)
        self.assertEqual(payload["think"], False)
        self.assertIsNone(request.get_header("Authorization"))

    def test_model_helpers(self) -> None:
        response = {"models": [{"name": "qwen3:8b", "model": "qwen3:8b"}]}
        self.assertEqual(model_names(response), {"qwen3:8b"})
        self.assertEqual(safe_model_name("qwen3:8b"), "qwen3_8b")
        self.assertIs(parse_think("off"), False)
        self.assertIs(parse_think("on"), True)
        self.assertEqual(parse_think("low"), "low")


if __name__ == "__main__":
    unittest.main()
