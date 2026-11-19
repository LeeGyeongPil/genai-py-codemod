"""Findings (spots the codemod did not or could not change) and report rendering."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from .i18n import Translator

Severity = Literal["manual", "info"]

# Reason codes. "manual" findings stop a file from being rewritten (all-or-nothing per file),
# "info" findings are notes about things that were converted but behave slightly differently.
CODES: dict[str, Severity] = {
    "handle-escapes": "manual",
    "handle-reassigned": "manual",
    "handle-untracked": "manual",
    "call-kwargs": "manual",
    "call-args": "manual",
    "call-config-merge": "manual",
    "config-dynamic": "manual",
    "callable-tools-afc": "manual",
    "tools-unsupported": "manual",
    "tool-config": "manual",
    "count-tokens-semantics": "manual",
    "async-chat": "manual",
    "history-format": "manual",
    "files-api": "manual",
    "caches-api": "manual",
    "tuning-api": "manual",
    "unsupported-api": "manual",
    "configure-args": "manual",
    "configure-scope": "manual",
    "mixed-sdk": "manual",
    "import-scope": "manual",
    "legacy-api": "manual",
    "response-shape": "info",
    "dynamic-model": "info",
}


@dataclass(frozen=True)
class Finding:
    """One spot in a source file worth a human look."""

    path: str
    line: int
    column: int
    code: str
    severity: Severity
    message_key: str

    def to_dict(self, translator: Translator | None = None) -> dict[str, object]:
        data: dict[str, object] = {
            "line": self.line,
            "column": self.column,
            "code": self.code,
            "severity": self.severity,
        }
        if translator is not None:
            data["message"] = translator(self.message_key)
        return data


def make_finding(path: str, line: int, column: int, code: str) -> Finding:
    return Finding(path, line, column, code, CODES[code], f"finding.{code}")


@dataclass
class FileReport:
    """Result for one file as shown by the command line."""

    path: str
    changed: bool = False
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None
    diff: str = ""


def render_finding(finding: Finding, translator: Translator) -> str:
    return f"{finding.path}:{finding.line} {finding.code} [{finding.severity}] {translator(finding.message_key)}"


def render_json(reports: list[FileReport], translator: Translator, *, mode: str) -> str:
    files = []
    for report in reports:
        entry: dict[str, object] = {
            "path": report.path,
            "changed": report.changed,
            "findings": [f.to_dict(translator) for f in report.findings],
        }
        if report.error:
            entry["error"] = report.error
        files.append(entry)
    manual = sum(1 for r in reports for f in r.findings if f.severity == "manual")
    summary = {
        "files": len(reports),
        "changed": sum(1 for r in reports if r.changed),
        "manual": manual,
        "info": sum(1 for r in reports for f in r.findings if f.severity == "info"),
        "errors": sum(1 for r in reports if r.error),
    }
    return json.dumps({"version": 1, "mode": mode, "summary": summary, "files": files}, ensure_ascii=False, indent=2)
