"""Command line interface: ``genai-py-codemod [paths]`` and ``genai-py-codemod verify BEFORE AFTER``."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import tokenize
from collections.abc import Iterator, Sequence
from io import BytesIO
from pathlib import Path
from typing import NoReturn

from . import __version__
from .i18n import SUPPORTED, Translator, resolve_lang
from .migrate import API_VERSION_MODES, ParseError, migrate_source
from .report import FileReport, render_finding, render_json

SKIP_DIRS = {"node_modules", "__pycache__", "build", "dist", "venv", "site-packages"}


def _preparse_lang(argv: Sequence[str]) -> str:
    """Find --lang before the real parser exists, so --help and usage errors are already translated.

    Scanned by hand: a throwaway argparse parser would print its own English error for ``--lang`` without a value.
    """
    value = None
    items = list(argv)
    for position, item in enumerate(items):
        if item == "--":
            break
        if item == "--lang" and position + 1 < len(items):
            value = items[position + 1]
        elif item.startswith("--lang="):
            value = item.split("=", 1)[1]
    return resolve_lang(value)


def _add_lang(parser: argparse.ArgumentParser, t: Translator) -> None:
    parser.add_argument("--lang", choices=SUPPORTED, default=None, help=t("arg.lang"))


class _Parser(argparse.ArgumentParser):
    """ArgumentParser whose built-in texts (usage, section titles, -h, errors) follow --lang."""

    def __init__(self, t: Translator, **kwargs: object) -> None:
        self._t = t
        kwargs["add_help"] = False
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._positionals.title = t("help.positional")
        self._optionals.title = t("help.options")
        self.add_argument("-h", "--help", action="help", help=t("help.help"))

    def format_usage(self) -> str:
        return super().format_usage().replace("usage: ", self._t("help.usage"), 1)

    def format_help(self) -> str:
        return super().format_help().replace("usage: ", self._t("help.usage"), 1)

    def error(self, message: str) -> NoReturn:
        t = self._t
        if m := re.match(r"the following arguments are required: (.*)", message):
            text = t("err.required", names=m.group(1))
        elif m := re.match(r"unrecognized arguments: (.*)", message):
            text = t("err.unrecognized", names=m.group(1))
        elif m := re.match(r"argument (.+?): invalid choice: (.+?) \(choose from (.*)\)", message):
            text = t("err.choice", name=m.group(1), value=m.group(2), choices=m.group(3).replace("'", ""))
        elif m := re.match(r"argument (.+?): expected one argument", message):
            text = t("err.expected", name=m.group(1))
        elif m := re.match(r"argument (.+?): invalid \w+ value: (.*)", message):
            text = t("err.invalid_value", name=m.group(1), value=m.group(2))  # e.g. --timeout abc
        elif m := re.match(r"argument (.+?): ignored explicit argument (.*)", message):
            text = t("err.ignored_value", name=m.group(1), value=m.group(2))  # e.g. --write=yes
        else:
            text = message  # argparse wording this tool's options cannot produce: shown as is
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: {t('err.prefix')}: {text}\n")


def build_parser(t: Translator) -> argparse.ArgumentParser:
    parser = _Parser(t, prog="genai-py-codemod", description=t("app.description"), epilog=t("app.epilog"))
    parser.add_argument("paths", nargs="+", metavar="PATH", help=t("arg.paths"))
    parser.add_argument("--write", action="store_true", help=t("arg.write"))
    parser.add_argument("--check", action="store_true", help=t("arg.check"))
    parser.add_argument("--report", choices=("text", "json"), default="text", help=t("arg.report"))
    parser.add_argument("--api-version", choices=API_VERSION_MODES, default="auto", help=t("arg.api_version"))
    _add_lang(parser, t)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}", help=t("app.version"))
    return parser


def build_verify_parser(t: Translator) -> argparse.ArgumentParser:
    parser = _Parser(t, prog="genai-py-codemod verify", description=t("verify.description"))
    parser.add_argument("before", metavar="BEFORE", help=t("verify.before"))
    parser.add_argument("after", metavar="AFTER", help=t("verify.after"))
    parser.add_argument("--old-python", default=None, metavar="PYTHON", help=t("verify.old_python"))
    parser.add_argument("--new-python", default=None, metavar="PYTHON", help=t("verify.new_python"))
    parser.add_argument("--json", action="store_true", help=t("verify.json"))
    parser.add_argument("--strict-version", action="store_true", help=t("verify.strict"))
    parser.add_argument("--timeout", type=float, default=60.0, metavar="SECONDS", help=t("verify.timeout"))
    _add_lang(parser, t)
    return parser


def iter_python_files(paths: Sequence[str], t: Translator) -> Iterator[Path]:
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            yield path
        elif path.is_dir():
            for found in sorted(path.rglob("*.py")):
                parts = found.relative_to(path).parts[:-1]
                if any(part in SKIP_DIRS or part.startswith(".") for part in parts):
                    continue
                yield found
        else:
            raise FileNotFoundError(t("msg.missing_path", path=raw))


def read_source(path: Path) -> tuple[str, str]:
    """Read a Python file following its PEP 263 encoding declaration, keeping line endings untouched."""
    raw = path.read_bytes()
    encoding, _ = tokenize.detect_encoding(BytesIO(raw).readline)
    return raw.decode(encoding), encoding  # decode() does not translate \r\n, unlike read_text()


def _color(text: str, code: str, enabled: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if enabled else text


def render_diff(path: str, old: str, new: str, color: bool) -> str:
    lines = difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile=path, tofile=path)
    out = []
    for line in lines:
        text = line.rstrip("\n")
        if text.startswith("+") and not text.startswith("+++"):
            text = _color(text, "32", color)
        elif text.startswith("-") and not text.startswith("---"):
            text = _color(text, "31", color)
        elif text.startswith("@@"):
            text = _color(text, "36", color)
        out.append(text)
    return "\n".join(out)


def run_migrate(args: argparse.Namespace, t: Translator) -> int:
    if args.write and args.check:
        print(t("msg.write_check_conflict"), file=sys.stderr)
        return 2
    try:
        files = list(iter_python_files(args.paths, t))
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 2
    if not files:
        print(t("msg.no_files", paths=", ".join(args.paths)), file=sys.stderr)
        return 2

    color = sys.stdout.isatty() and "NO_COLOR" not in os.environ and args.report == "text"
    reports: list[FileReport] = []
    errors = 0
    for path in files:
        report = FileReport(path=str(path))
        reports.append(report)
        try:
            source, encoding = read_source(path)
        except (OSError, UnicodeDecodeError, SyntaxError, LookupError) as error:
            report.error = t("msg.read_error", path=path, detail=error)
            errors += 1
            continue
        try:
            result = migrate_source(source, path=str(path), api_version=args.api_version)
        except ParseError as error:
            report.error = t("msg.parse_error", path=error.path, line=error.line, message=error.message)
            errors += 1
            continue
        report.findings = result.findings
        report.changed = result.changed
        if result.changed:
            report.diff = render_diff(str(path), source, result.code, color)
            if args.write:
                try:
                    with open(path, "w", encoding=encoding, newline="") as handle:  # newline="" keeps CRLF as is
                        handle.write(result.code)
                except OSError as error:
                    report.error = t("msg.write_error", path=path, detail=error)
                    errors += 1

    manual = sum(1 for r in reports for f in r.findings if f.severity == "manual")
    info = sum(1 for r in reports for f in r.findings if f.severity == "info")
    changed = sum(1 for r in reports if r.changed)

    if args.report == "json":
        mode = "write" if args.write else "check" if args.check else "dry-run"
        print(render_json(reports, t, mode=mode))
    else:
        for report in reports:
            if report.error:
                print(report.error, file=sys.stderr)
        if not args.check:
            for report in reports:
                if report.diff:
                    print(report.diff)
                    if args.write:
                        print(t("msg.written", path=report.path))
        for report in reports:
            for finding in report.findings:
                print(render_finding(finding, t))
        key = "summary.written" if args.write else "summary.check" if args.check else "summary.dry_run"
        print(t(key, changed=changed, manual=manual, info=info, scanned=len(files)))

    if errors:
        return 2
    if args.check and (changed or manual):
        return 1
    return 0


def run_verify(argv: Sequence[str], t: Translator) -> int:
    from .verify import VerifyRunError, verify_files
    from .verify.compare import render_version_change

    args = build_verify_parser(t).parse_args(list(argv))
    try:
        result = verify_files(
            args.before,
            args.after,
            old_python=args.old_python,
            new_python=args.new_python,
            strict_version=args.strict_version,
            timeout=args.timeout,
        )
    except VerifyRunError as error:
        if args.json:
            # error 는 언어와 무관한 코드, message 는 고른 언어의 문장(보고서 findings 와 같은 방식)
            payload = {"equivalent": None, "error": error.code, "message": error.message(t)}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(t("verify.error", detail=error.message(t)), file=sys.stderr)
            if error.hint:
                print(t(f"verify.hint.{error.hint}"), file=sys.stderr)
        return 2
    if args.json:
        print(
            json.dumps(
                {
                    "equivalent": result.equivalent,
                    "nothing_compared": result.nothing_compared,
                    "requests": {"before": len(result.requests_before), "after": len(result.requests_after)},
                    "diffs": [
                        {"request": d.index, "method": d.method, "path": d.path, "before": d.before, "after": d.after}
                        for d in result.diffs
                    ],
                    "warnings": [render_version_change(change, t) for change in result.version_changes],
                    "version_changes": [{"before": old, "after": new} for old, new in result.version_changes],
                    "network_attempts": result.network_attempts,
                    "sdk_versions": result.sdk_versions,
                    "mock": True,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        if result.nothing_compared:
            print(t("verify.nothing"))
        elif result.equivalent:
            print(t("verify.equivalent", count=len(result.requests_after)))
        else:
            print(t("verify.different", count=len(result.diffs)))
            for diff in result.diffs:
                print("  " + diff.render(t))
        for change in result.version_changes:
            print(t("verify.warning", text=render_version_change(change, t)))
        if result.network_attempts:
            print(t("verify.network", count=result.network_attempts))
        print(t("verify.mock_notice"))
    if result.nothing_compared:
        return 2  # could not prove anything: not "same", not "different"
    return 0 if result.equivalent else 1


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    t = Translator(_preparse_lang(args_list))
    if args_list and args_list[0] == "verify":
        return run_verify(args_list[1:], t)
    args = build_parser(t).parse_args(args_list)
    if args.lang:
        t = Translator(args.lang)
    return run_migrate(args, t)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
