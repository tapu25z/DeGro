from __future__ import annotations

import json
import http.client
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class OllamaCloudError(RuntimeError):
    pass


def load_api_keys(path: str | Path) -> tuple[str, ...]:
    """Load one key per line.

    Comments, ``NAME=value`` lines, and human labels followed by a whitespace-
    separated key are accepted. Only the final field of a labelled line is used.
    """
    keys: list[str] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            line = line.split("=", 1)[1].strip().strip("'\"")
        elif any(character.isspace() for character in line):
            line = line.split()[-1].strip("'\"")
        if line:
            keys.append(line)
    if not keys:
        raise ValueError(f"no API keys found in {path}")
    return tuple(keys)


@dataclass(frozen=True)
class Attempt:
    account_index: int
    status: int | None
    category: str


class OllamaCloudClient:
    """Minimal Ollama Cloud client with bounded account failover.

    Key values are never included in errors or attempt metadata. A request starts
    at the last successful account. Authentication, quota, and rate-limit errors
    advance to the next account; transient server errors receive a short retry.
    """

    _ROTATE_STATUSES = frozenset({401, 402, 403, 429})
    _RETRY_STATUSES = frozenset({500, 502, 503, 504})

    def __init__(
        self,
        api_keys: tuple[str, ...],
        host: str = "https://ollama.com",
        timeout_s: float = 120.0,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        if not api_keys:
            raise ValueError("at least one API key is required")
        self._keys = api_keys
        self.host = host.rstrip("/")
        self.timeout_s = timeout_s
        self._opener = opener
        self._preferred = 0
        self.last_attempts: tuple[Attempt, ...] = ()

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        format_schema: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        think: str | bool | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if format_schema is not None:
            payload["format"] = format_schema
        if options:
            payload["options"] = options
        if think is not None:
            payload["think"] = think
        return self._request("/api/chat", payload)

    def list_models(self) -> dict[str, Any]:
        return self._request("/api/tags", None)

    def _request(self, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        attempts: list[Attempt] = []
        errors: list[str] = []
        order = [(self._preferred + offset) % len(self._keys) for offset in range(len(self._keys))]
        for account_index in order:
            for transient_try in range(2):
                request = urllib.request.Request(
                    self.host + path,
                    data=body,
                    method="GET" if body is None else "POST",
                    headers={
                        "Authorization": f"Bearer {self._keys[account_index]}",
                        "Content-Type": "application/json",
                        "User-Agent": "targetcheck/0.1",
                    },
                )
                try:
                    with self._opener(request, timeout=self.timeout_s) as response:
                        result = json.loads(response.read().decode("utf-8"))
                    attempts.append(Attempt(account_index + 1, 200, "success"))
                    self._preferred = account_index
                    self.last_attempts = tuple(attempts)
                    return result
                except urllib.error.HTTPError as exc:
                    status = exc.code
                    if status in self._RETRY_STATUSES and transient_try == 0:
                        attempts.append(Attempt(account_index + 1, status, "transient_retry"))
                        time.sleep(0.5)
                        continue
                    category = "rotate" if status in self._ROTATE_STATUSES else "http_error"
                    attempts.append(Attempt(account_index + 1, status, category))
                    errors.append(f"account {account_index + 1}: HTTP {status}")
                    if status not in self._ROTATE_STATUSES:
                        self.last_attempts = tuple(attempts)
                        raise OllamaCloudError(errors[-1]) from exc
                    break
                except (
                    urllib.error.URLError,
                    TimeoutError,
                    ConnectionError,
                    http.client.RemoteDisconnected,
                    json.JSONDecodeError,
                ) as exc:
                    attempts.append(Attempt(account_index + 1, None, "network_error"))
                    errors.append(f"account {account_index + 1}: network error")
                    if transient_try == 0:
                        time.sleep(0.5)
                        continue
                    break
        self.last_attempts = tuple(attempts)
        raise OllamaCloudError("all configured accounts failed (" + "; ".join(errors) + ")")
