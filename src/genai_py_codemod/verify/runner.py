"""Run one script with mocked Gemini transports and record the API requests it sends.

Usage: ``python -I runner.py <target.py> <result.json>``

This file uses the standard library only: it is executed by the interpreter that has the SDK under test installed
(the old SDK for the "before" file, the new one for the "after" file), which may not be the interpreter that runs
``genai-py-codemod``. It never opens a network connection: socket connects are blocked and every SDK transport is
replaced by a mock that returns fixed responses. The requests are built by the real SDK code, so what is recorded is
what the SDK would have sent.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import runpy
import socket
import sys
import traceback
import warnings
from typing import Any

FAKE_KEY = "FAKE-KEY"
records: list[dict[str, Any]] = []
network_attempts: list[str] = []
sdk_versions: dict[str, str] = {}

MODEL_TEXT = "mock response"
GENERATE_BODY = {
    "candidates": [
        {"content": {"parts": [{"text": MODEL_TEXT}], "role": "model"}, "finishReason": "STOP", "index": 0}
    ],
    "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2, "totalTokenCount": 5},
}
STREAM_CHUNKS = [
    {"candidates": [{"content": {"parts": [{"text": "mock "}], "role": "model"}, "index": 0}]},
    {
        "candidates": [{"content": {"parts": [{"text": "stream"}], "role": "model"}, "finishReason": "STOP", "index": 0}],
        "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2, "totalTokenCount": 5},
    },
]


def canned(path: str, query: str) -> tuple[bytes, str]:
    """Fixed response for an endpoint; returns (body, content type)."""
    if ":streamGenerateContent" in path:
        if "alt=sse" in query:
            body = "".join(f"data: {json.dumps(chunk)}\r\n\r\n" for chunk in STREAM_CHUNKS)
            return body.encode(), "text/event-stream"
        return json.dumps(STREAM_CHUNKS).encode(), "application/json"
    if path.endswith(":countTokens"):
        return json.dumps({"totalTokens": 7}).encode(), "application/json"
    if path.endswith(":embedContent"):
        return json.dumps({"embedding": {"values": [0.1, 0.2, 0.3]}}).encode(), "application/json"
    if path.endswith(":batchEmbedContents"):
        return json.dumps({"embeddings": [{"values": [0.1, 0.2, 0.3]}]}).encode(), "application/json"
    return json.dumps(GENERATE_BODY).encode(), "application/json"


def record(sdk: str, method: str, path: str, query: str, body: bytes | str | None, source: str) -> None:
    parsed: Any = None
    if body:
        text = body.decode() if isinstance(body, bytes) else body
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = {"__raw__": text}
    if sdk == "old":
        parsed = name_enums(parsed, source)
    records.append({"sdk": sdk, "method": method, "path": path, "query": query, "body": parsed})


# -- old SDK sends integer enums (enum-encoding=int); turn them back into names ---------------------------------
def _enum_tables(source: str) -> dict[str, Any]:
    tables: dict[str, Any] = {}
    try:
        if source == "vertex":
            from google.cloud.aiplatform_v1.types import content, openapi  # type: ignore

            tables["category"] = content.HarmCategory
            tables["threshold"] = content.SafetySetting.HarmBlockThreshold
            tables["type"] = openapi.Type
        else:
            from google.ai.generativelanguage_v1beta.types import content, generative_service, safety  # type: ignore

            tables["category"] = safety.HarmCategory
            tables["threshold"] = safety.SafetySetting.HarmBlockThreshold
            tables["taskType"] = generative_service.TaskType
            tables["type"] = content.Type
    except Exception:  # pragma: no cover - depends on the installed SDK
        pass
    return tables


def name_enums(value: Any, source: str) -> Any:
    tables = _enum_tables(source)

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            out = {}
            for key, item in node.items():
                if key in tables and isinstance(item, int) and not isinstance(item, bool):
                    try:
                        item = tables[key](item).name
                    except ValueError:
                        pass
                out[key] = walk(item)
            return out
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(value)


# -- network guard ---------------------------------------------------------------------------------------------
class NetworkBlocked(OSError):
    """Raised inside the checked script when it tries to connect; the CLI shows a translated message instead."""


def block_network() -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        network_attempts.append(repr(args[1:2] or args[:1]))
        raise NetworkBlocked("network access is blocked by genai-py-codemod verify")

    socket.socket.connect = refuse  # type: ignore[method-assign]
    socket.socket.connect_ex = refuse  # type: ignore[method-assign]
    socket.create_connection = refuse  # type: ignore[assignment]
    socket.getaddrinfo = refuse  # type: ignore[assignment]


def fake_credentials() -> Any:
    from google.oauth2.credentials import Credentials

    return Credentials(token="fake-token")


# -- old SDKs -------------------------------------------------------------------------------------------------------
def install_requests_mock() -> None:
    import requests

    def fake_send(self: Any, request: Any, **kwargs: Any) -> Any:
        url = request.url
        host_match = re.match(r"https?://([^/]+)(/[^?]*)\??(.*)", url)
        host, path, query = host_match.groups() if host_match else ("", url, "")
        source = "vertex" if "aiplatform" in host else "developer"
        record("old", request.method, path, query, request.body, source)
        body, content_type = canned(path, query)
        response = requests.Response()
        response.status_code = 200
        response._content = body
        response._content_consumed = True
        response.encoding = "utf-8"
        response.headers["content-type"] = content_type
        response.url = url
        response.request = request
        return response

    requests.Session.send = fake_send  # type: ignore[method-assign]


def install_old_developer() -> None:
    import google.generativeai as old  # type: ignore

    sdk_versions["google-generativeai"] = getattr(old, "__version__", "unknown")
    original = old.configure

    def configure(*args: Any, **kwargs: Any) -> Any:
        kwargs["transport"] = "rest"
        return original(*args, **kwargs)

    old.configure = configure
    original(api_key=FAKE_KEY, transport="rest")  # scripts that rely on environment variables


def install_old_vertex() -> None:
    import vertexai  # type: ignore

    sdk_versions["vertexai"] = getattr(vertexai, "__version__", "unknown")
    original = vertexai.init

    def init(*args: Any, **kwargs: Any) -> Any:
        kwargs["api_transport"] = "rest"
        kwargs["credentials"] = fake_credentials()
        kwargs.setdefault("project", "mock-project")
        kwargs.setdefault("location", "us-central1")
        return original(*args, **kwargs)

    vertexai.init = init


# -- new SDK ---------------------------------------------------------------------------------------------------------
def install_new() -> None:
    from google import genai
    from google.genai import types

    version = getattr(genai, "__version__", "0")
    sdk_versions["google-genai"] = version
    try:
        if int(version.split(".")[0]) >= 3:
            import httpx2 as httpx_module  # type: ignore
        else:
            import httpx as httpx_module  # type: ignore
    except ImportError:
        import httpx as httpx_module  # type: ignore

    def handler(request: Any) -> Any:
        path = request.url.path
        query = request.url.query.decode() if isinstance(request.url.query, bytes) else str(request.url.query)
        source = "vertex" if "aiplatform" in str(request.url.host) else "developer"
        record("new", request.method, path, query, request.content, source)
        body, content_type = canned(path, query)
        return httpx_module.Response(200, content=body, headers={"content-type": content_type})

    original_init = genai.Client.__init__

    def init(self: Any, *args: Any, **kwargs: Any) -> Any:
        options = kwargs.get("http_options")
        if options is None:
            options = types.HttpOptions()
        elif isinstance(options, dict):
            options = types.HttpOptions(**options)
        options = options.model_copy(
            update={
                "httpx_client": httpx_module.Client(transport=httpx_module.MockTransport(handler)),
                "httpx_async_client": httpx_module.AsyncClient(transport=httpx_module.MockTransport(handler)),
            }
        )
        kwargs["http_options"] = options
        if kwargs.get("vertexai") and "credentials" not in kwargs:
            kwargs["credentials"] = fake_credentials()
        return original_init(self, *args, **kwargs)

    genai.Client.__init__ = init  # type: ignore[method-assign]


def _source_path(path: str) -> str:
    # runpy.__file__ 이 .pyc 로 잡히는 배포판도 있어 .py 로 맞춘 뒤 실제 경로끼리 비교한다
    if path.endswith((".pyc", ".pyo")):
        path = path[:-1]
    return os.path.normcase(os.path.realpath(path))


# traceback 에서 빼는 파일: 이 runner 자신과 runpy. 3.11+ 은 runpy 줄이 "<frozen runpy>" 로 찍히지만
# 3.9·3.10 은 ".../runpy.py" 실제 경로로 찍혀서 이름 접두만으로는 걸러지지 않는다.
_INTERNAL_FILES = {_source_path(__file__), _source_path(runpy.__file__ or "runpy.py")}


def is_internal_frame(filename: str) -> bool:
    """True for traceback lines that belong to the runner itself, not to the checked script."""
    if filename.startswith("<frozen"):
        return True
    return _source_path(filename) in _INTERNAL_FILES


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: runner.py <target.py> <result.json>", file=sys.stderr)
        return 64
    target, out_path = argv[1], argv[2]
    warnings.filterwarnings("ignore")
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        os.environ[name] = FAKE_KEY
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "mock-project")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
    for name in ("GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_APPLICATION_CREDENTIALS"):
        os.environ.pop(name, None)
    block_network()

    with open(target, encoding="utf-8") as handle:
        text = handle.read()
    # 실패 원인은 문장이 아니라 코드(error_code)로 남긴다. 문장은 CLI 가 고른 언어의 메시지 표에서 만든다.
    error_code: str | None = None
    error: str | None = None  # 원인 진단용 원문(파이썬 예외·traceback), 번역 대상 아님
    exit_code = 0
    try:
        wants_old_dev = re.search(r"^\s*(import|from)\s+google(\.generativeai\b|\s+import\s+generativeai\b)", text, re.M)
        wants_vertex = re.search(r"^\s*(import|from)\s+vertexai\b", text, re.M)
        wants_new = re.search(r"^\s*(import|from)\s+google(\.genai\b|\s+import\s+genai\b)", text, re.M)
        if wants_old_dev or wants_vertex:
            install_requests_mock()
        if wants_old_dev:
            install_old_developer()
        if wants_vertex:
            install_old_vertex()
        if wants_new:
            install_new()
        sys.path.insert(0, os.path.dirname(os.path.abspath(target)))
        sys.argv = [target]
        with contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(target, run_name="__main__")
    except SystemExit as stop:
        if stop.code not in (None, 0):
            error_code, error, exit_code = "script-exit", str(stop.code), 3
    except BaseException as exc:  # noqa: BLE001 - report everything the target raised
        # 검사한 스크립트의 줄만 보여 준다(runner·runpy 내부 줄은 사용자에게 의미가 없다)
        frames = [frame for frame in traceback.extract_tb(exc.__traceback__) if not is_internal_frame(frame.filename)]
        where = "".join(traceback.format_list(frames[-3:])).rstrip()
        if isinstance(exc, NetworkBlocked):
            error_code, error = "network-blocked", where  # 막은 쪽이 우리라서 예외 문장 대신 위치만 남긴다
        else:
            error_code = "sdk-missing" if isinstance(exc, ImportError) else "script-failed"
            error = "".join(traceback.format_exception_only(type(exc), exc)).strip() + "\n" + where
        exit_code = 3
    result = {
        "requests": records,
        "network_attempts": len(network_attempts),
        "sdk_versions": sdk_versions,
        "error_code": error_code,
        "error": error,
    }
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
