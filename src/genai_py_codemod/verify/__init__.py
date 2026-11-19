"""Request-equivalence check: run the file before and after a migration against mocked transports."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..i18n import Translator, english
from .compare import Diff, NormalizedRequest, compare_requests, normalize_request, render_version_change

RUNNER = Path(__file__).with_name("runner.py")
_ENV_KEEP = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT", "TEMP", "TMP")

# Failure codes; the sentence for each is ``verify.error.<code>`` in the message catalog (locales/*.json).
ERROR_CODES = (
    "missing-file",
    "interpreter-not-found",
    "timeout",
    "no-result",
    "script-exit",
    "script-failed",
    "sdk-missing",
    "network-blocked",
)


class VerifyRunError(RuntimeError):
    """The file could not be run to the end (error in the file, timeout, SDK not installed).

    ``code`` is one of :data:`ERROR_CODES` and ``params`` fills the message; ``str(error)`` is the English
    message and :meth:`message` gives it in another language. ``hint`` is ``"old-sdk"`` / ``"new-sdk"`` when the
    cause is a missing SDK, so a front end can add a translated "how to fix" line.
    """

    def __init__(self, code: str, *, hint: str | None = None, **params: object) -> None:
        self.code = code
        self.params = params
        self.hint = hint
        super().__init__(self.message())

    def message(self, translator: Translator | None = None) -> str:
        # 문장은 메시지 표 한 곳에서만 만든다: 라이브러리는 영어, CLI 는 --lang 으로 고른 언어
        return (translator or english())(f"verify.error.{self.code}", **self.params)


@dataclass
class VerifyResult:
    equivalent: bool
    requests_before: list[NormalizedRequest]
    requests_after: list[NormalizedRequest]
    diffs: list[Diff] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    network_attempts: int = 0
    sdk_versions: dict[str, str] = field(default_factory=dict)
    version_changes: list[tuple[str, str]] = field(default_factory=list)

    @property
    def nothing_compared(self) -> bool:
        """True when neither file sent a request: there is nothing to prove equivalence with."""
        return not self.requests_before and not self.requests_after


def _run(python: str, target: Path, timeout: float, side: str) -> dict[str, Any]:
    if not target.is_file():
        raise VerifyRunError("missing-file", path=target)
    if os.sep in python or (os.altsep and os.altsep in python):
        python = os.path.abspath(python)  # keep the venv symlink; the child runs in another directory
    env = {key: os.environ[key] for key in _ENV_KEEP if key in os.environ}
    with tempfile.TemporaryDirectory(prefix="genai-py-codemod-") as scratch:
        out = Path(scratch) / "result.json"
        command = [python, "-I", str(RUNNER), str(target.resolve()), str(out)]
        try:
            # 시간 초과면 subprocess.run 이 자식을 kill 하고 기다린 뒤 TimeoutExpired 를 낸다(자식이 남지 않음)
            completed = subprocess.run(
                command, cwd=scratch, env=env, capture_output=True, text=True, timeout=timeout, check=False
            )
        except FileNotFoundError as error:
            raise VerifyRunError("interpreter-not-found", python=python) from error
        except subprocess.TimeoutExpired as error:
            raise VerifyRunError("timeout", path=target, seconds=f"{timeout:g}") from error
        if not out.exists():
            tail = (completed.stderr or completed.stdout).strip()[-800:]
            raise VerifyRunError("no-result", path=target, python=python, detail=tail)
        result = json.loads(out.read_text(encoding="utf-8"))
    code = result.get("error_code")
    if code:
        detail = (result.get("error") or "").strip("\n")  # keep the indentation of traceback lines
        hint = f"{side}-sdk" if code == "sdk-missing" else None
        if code == "script-exit":
            raise VerifyRunError(code, path=target, python=python, status=detail)
        raise VerifyRunError(code, hint=hint, path=target, python=python, detail=detail)
    return result


def verify_files(
    before: Path | str,
    after: Path | str,
    *,
    old_python: str | None = None,
    new_python: str | None = None,
    strict_version: bool = False,
    timeout: float = 60,
) -> VerifyResult:
    """Run ``before`` and ``after`` with mocked transports and compare the API requests they send.

    ``old_python`` runs ``before`` (default: the current interpreter), ``new_python`` runs ``after``.
    """
    before_path, after_path = Path(before), Path(after)
    old_python = old_python or sys.executable
    new_python = new_python or sys.executable
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_run, old_python, before_path, timeout, "old")
        second = pool.submit(_run, new_python, after_path, timeout, "new")
        before_result, after_result = first.result(), second.result()
    requests_before = [normalize_request(r) for r in before_result["requests"]]
    requests_after = [normalize_request(r) for r in after_result["requests"]]
    diffs, version_changes = compare_requests(requests_before, requests_after)
    if strict_version:
        diffs.extend(Diff(0, "version", "api_version", old, new, kind="version") for old, new in version_changes)
    versions = {**before_result.get("sdk_versions", {}), **after_result.get("sdk_versions", {})}
    nothing_compared = not requests_before and not requests_after
    return VerifyResult(
        equivalent=not diffs and not nothing_compared,  # zero requests on both sides proves nothing
        requests_before=requests_before,
        requests_after=requests_after,
        diffs=diffs,
        warnings=[render_version_change(change) for change in version_changes],  # English, for the library
        network_attempts=int(before_result.get("network_attempts", 0)) + int(after_result.get("network_attempts", 0)),
        sdk_versions=versions,
        version_changes=version_changes,
    )


__all__ = ["ERROR_CODES", "Diff", "NormalizedRequest", "VerifyResult", "VerifyRunError", "verify_files"]
