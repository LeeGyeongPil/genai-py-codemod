"""Normalize recorded requests and compare them (pure functions, no SDK needed)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..i18n import Translator, english

MISSING = "(missing)"
_VERSION = re.compile(r"^v\d+(?:alpha|beta)?\d*$")
_MODEL_METHOD = re.compile(r"(?:^|/)models/([^/:]+):(\w+)$")


@dataclass(frozen=True)
class NormalizedRequest:
    """One request reduced to what has to stay the same after a migration."""

    method: str  # e.g. generateContent
    model: str
    version: str
    body: Any

    def summary(self) -> str:
        return f"{self.method} {self.model}"


@dataclass(frozen=True)
class Diff:
    """One difference: which request, where in the body, what changed.

    ``kind`` is ``"body"`` (a path inside the request body), ``"count"`` (number of requests), ``"method"``,
    ``"model"`` or ``"version"`` (API version, only with ``strict_version``).
    """

    index: int
    method: str
    path: str
    before: Any
    after: Any
    kind: str = "body"

    def render(self, translator: Translator | None = None) -> str:
        """One line for people; the fixed words come from the message catalog (English by default)."""
        t = translator or english()
        if self.kind == "version":
            return t("verify.diff.version", before=self.before or "?", after=self.after or "?")
        before, after = _show(self.before, t), _show(self.after, t)
        if self.kind == "body":
            # 본문 경로·값은 데이터라 번역하지 않는다(고정 낱말 없음)
            return f"{self.method} #{self.index} {self.path}: {before} -> {after}"
        return t(f"verify.diff.{self.kind}", method=self.method, index=self.index, before=before, after=after)


def _show(value: Any, t: Translator) -> str:
    import json

    if value == MISSING:
        return t("verify.diff.missing")
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def render_version_change(change: tuple[str, str], translator: Translator | None = None) -> str:
    """'API version v1beta -> v1' in the chosen language."""
    t = translator or english()
    return t("verify.warning.api_version", before=change[0] or "?", after=change[1] or "?")


def _camel(key: str) -> str:
    return re.sub(r"_([a-z0-9])", lambda match: match.group(1).upper(), key)


def _clean(node: Any) -> Any:
    """camelCase keys, drop empty values (``None``, ``{}``, ``[]``)."""
    if isinstance(node, dict):
        out = {}
        for key in sorted(node):
            value = _clean(node[key])
            if value is None or value == {} or value == []:
                continue
            out[_camel(key)] = value
        return out
    if isinstance(node, list):
        return [_clean(item) for item in node]
    return node


def normalize_request(record: dict[str, Any]) -> NormalizedRequest:
    path = record["path"].strip("/")
    segments = path.split("/", 1)
    version = segments[0] if _VERSION.match(segments[0]) else ""
    rest = segments[1] if version and len(segments) > 1 else path
    match = _MODEL_METHOD.search(rest)
    model, method = (match.group(1), match.group(2)) if match else ("", rest)
    body = _clean(record.get("body"))
    if isinstance(body, dict):
        body = _normalize_body(method, body)
    return NormalizedRequest(method, model, version, body)


def _without_role(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: v for k, v in node.items() if k != "role"}
    return node


def _default_user_role(contents: Any) -> Any:
    """A content without a role is a user turn; the new SDK writes the role out, the old one may not."""
    if isinstance(contents, list):
        return [{"role": "user", **item} if isinstance(item, dict) and "role" not in item else item for item in contents]
    return contents


def _normalize_body(method: str, body: dict[str, Any]) -> dict[str, Any]:
    if method == "countTokens" and "generateContentRequest" in body:
        # The old SDK wraps contents (and model settings) into generateContentRequest; the new one sends contents.
        wrapped = {
            k: v
            for k, v in body["generateContentRequest"].items()
            if k not in ("model", "safetySettings", "generationConfig")
        }
        body = {**{k: v for k, v in body.items() if k != "generateContentRequest"}, **wrapped}
    if method == "countTokens":
        body = {k: v for k, v in body.items() if k != "model"}  # the model is part of the URL
    if "systemInstruction" in body:
        body = {**body, "systemInstruction": _without_role(body["systemInstruction"])}  # same meaning server-side
    if "contents" in body:
        body = {**body, "contents": _default_user_role(body["contents"])}
    if method in ("embedContent", "batchEmbedContents"):
        items = body["requests"] if "requests" in body else [body]
        body = {
            "requests": [
                {
                    k: (_without_role(v) if k == "content" and isinstance(v, dict) and v.get("role") == "user" else v)
                    for k, v in item.items()
                    if k != "model"  # the model is part of the URL
                }
                for item in items
            ]
        }
    return body


def canonical_method(method: str) -> str:
    return "embed" if method in ("embedContent", "batchEmbedContents") else method


def deep_diff(before: Any, after: Any, path: str = "body") -> list[tuple[str, Any, Any]]:
    """Path-level differences between two JSON-like values."""
    if isinstance(before, dict) and isinstance(after, dict):
        found = []
        for key in sorted(set(before) | set(after)):
            found.extend(deep_diff(before.get(key, MISSING), after.get(key, MISSING), f"{path}.{key}"))
        return found
    if isinstance(before, list) and isinstance(after, list):
        found = []
        for index in range(max(len(before), len(after))):
            left = before[index] if index < len(before) else MISSING
            right = after[index] if index < len(after) else MISSING
            found.extend(deep_diff(left, right, f"{path}[{index}]"))
        return found
    return [] if before == after else [(path, before, after)]


def compare_requests(
    before: list[NormalizedRequest], after: list[NormalizedRequest]
) -> tuple[list[Diff], list[tuple[str, str]]]:
    """Compare two ordered request lists. Returns (diffs, API version changes as (before, after) pairs)."""
    diffs: list[Diff] = []
    versions: list[tuple[str, str]] = []
    if len(before) != len(after):
        diffs.append(Diff(0, "requests", "count", len(before), len(after), kind="count"))
    for number, (left, right) in enumerate(zip(before, after, strict=False), start=1):
        if canonical_method(left.method) != canonical_method(right.method):
            diffs.append(Diff(number, left.method, "method", left.method, right.method, kind="method"))
            continue
        if left.model != right.model:
            diffs.append(Diff(number, left.method, "model", left.model, right.model, kind="model"))
        for path, old, new in deep_diff(left.body, right.body):
            diffs.append(Diff(number, left.method, path, old, new))
        change = (left.version, right.version)
        if left.version != right.version and change not in versions:
            versions.append(change)  # 문장은 화면에서 고른 언어로 만든다
    return diffs, versions
