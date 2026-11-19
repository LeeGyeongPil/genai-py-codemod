"""Public entry point of the codemod: :func:`migrate_source`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import libcst as cst
from libcst.metadata import MetadataWrapper

from .report import Finding
from .tracker import Analyzer
from .transform import Migrator, TypeRenamer, fix_imports

ApiVersionMode = Literal["auto", "keep", "none"]
API_VERSION_MODES = ("auto", "keep", "none")


class ParseError(ValueError):
    """The source could not be parsed; carries the file path and the line of the syntax error."""

    def __init__(self, path: str, line: int, message: str) -> None:
        super().__init__(f"{path}:{line}: {message}")
        self.path = path
        self.line = line
        self.message = message


@dataclass
class MigrationResult:
    """New source text, whether it differs from the input, and the spots that need a human look."""

    code: str
    changed: bool
    findings: list[Finding] = field(default_factory=list)

    @property
    def manual(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "manual"]


def migrate_source(
    source: str, *, path: str = "<string>", api_version: ApiVersionMode = "auto"
) -> MigrationResult:
    """Move ``google-generativeai`` / ``vertexai.generative_models`` code to ``google-genai``.

    A file is migrated completely or not at all: if any spot cannot be followed safely, ``code`` is the unchanged
    input and ``findings`` lists the spots (``severity == "manual"``).
    """
    if api_version not in API_VERSION_MODES:
        raise ValueError(f"api_version must be one of {', '.join(API_VERSION_MODES)}; got {api_version!r}")
    try:
        module = cst.parse_module(source)
    except cst.ParserSyntaxError as error:
        raise ParseError(path, error.raw_line, error.message) from error
    if "generativeai" not in source and "vertexai" not in source:
        return MigrationResult(source, False, [])

    wrapper = MetadataWrapper(module)
    analyzer = Analyzer(path)
    wrapper.visit(analyzer)
    analysis = analyzer.finish()
    migrator = Migrator(analysis, path, api_version)
    transformed = wrapper.visit(migrator)

    findings = _sorted(analysis.findings + migrator.findings)
    if any(f.severity == "manual" and f.code != "legacy-api" for f in findings):
        # "legacy-api" is only a consequence of the other manual spots; do not list it twice.
        findings = [f for f in findings if f.code != "legacy-api"]
    if any(f.severity == "manual" for f in findings):
        return MigrationResult(source, False, findings)

    code = transformed.code
    renamer_wrapper = MetadataWrapper(cst.parse_module(code))
    code = renamer_wrapper.visit(TypeRenamer(analysis.types_name)).code
    code = fix_imports(code, analysis.types_name, analysis.genai_name)
    return MigrationResult(code, code != source, findings)


def _sorted(findings: list[Finding]) -> list[Finding]:
    seen: set[Finding] = set()
    unique = []
    for finding in findings:
        if finding not in seen:
            seen.add(finding)
            unique.append(finding)
    return sorted(unique, key=lambda f: (f.line, f.column, f.code))
