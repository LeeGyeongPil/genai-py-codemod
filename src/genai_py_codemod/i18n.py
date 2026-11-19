"""Language selection (English / Korean) and message lookup.

Order of precedence: ``--lang`` option > ``GENAI_PY_CODEMOD_LANG`` > ``LC_ALL`` / ``LC_MESSAGES`` / ``LANG``.
Anything that does not start with ``ko`` falls back to English.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from functools import cache
from importlib import resources

SUPPORTED = ("en", "ko")
ENV_VAR = "GENAI_PY_CODEMOD_LANG"


def _normalize(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    if not value or value in ("c", "posix"):
        return None
    return "ko" if value.startswith("ko") else "en"


def resolve_lang(cli_value: str | None = None, env: Mapping[str, str] | None = None) -> str:
    """Pick the UI language. Unknown values fall back to English."""
    env = os.environ if env is None else env
    for candidate in (cli_value, env.get(ENV_VAR), env.get("LC_ALL"), env.get("LC_MESSAGES"), env.get("LANG")):
        chosen = _normalize(candidate)
        if chosen:
            return chosen
    return "en"


@cache
def load_messages(lang: str) -> dict[str, str]:
    if lang not in SUPPORTED:
        raise ValueError(f"unsupported language {lang!r}; choose one of: {', '.join(SUPPORTED)}")
    text = resources.files("genai_py_codemod").joinpath("locales", f"{lang}.json").read_text(encoding="utf-8")
    return json.loads(text)


class Translator:
    """Callable that returns the message for a key in a fixed language."""

    def __init__(self, lang: str) -> None:
        self.lang = lang
        self._messages = load_messages(lang)
        self._fallback = load_messages("en")

    def __call__(self, key: str, **params: object) -> str:
        template = self._messages.get(key) or self._fallback.get(key) or key
        return template.format(**params) if params else template


@cache
def english() -> Translator:
    """English translator for library-level texts (exception messages, ``VerifyResult.warnings``)."""
    return Translator("en")
