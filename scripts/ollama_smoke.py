#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from targetcheck.providers import OllamaCloudClient, load_api_keys


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe Ollama Cloud account-rotation smoke test")
    parser.add_argument("--keys", type=Path, default=Path("api.txt"))
    parser.add_argument("--model", default="gpt-oss:20b")
    parser.add_argument("--list-only", action="store_true")
    args = parser.parse_args()
    client = OllamaCloudClient(load_api_keys(args.keys), timeout_s=180)
    if args.list_only:
        response = client.list_models()
        names = [model.get("name", model.get("model", "")) for model in response.get("models", [])]
        print(json.dumps({"models": names, "attempts": [a.__dict__ for a in client.last_attempts]}))
        return
    response = client.chat(
        args.model,
        [{"role": "user", "content": "Return exactly the JSON object {\"ok\": true}."}],
        format_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
        options={"temperature": 0},
        think=False,
    )
    print(json.dumps({
        "model": response.get("model"),
        "content": response.get("message", {}).get("content"),
        "attempts": [a.__dict__ for a in client.last_attempts],
    }))


if __name__ == "__main__":
    main()
