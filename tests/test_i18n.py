"""AC-10: English / Korean messages, identical key sets, language precedence."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from conftest import FIXTURES

from genai_py_codemod import i18n
from genai_py_codemod.cli import main
from genai_py_codemod.report import CODES

LOCALES = Path(i18n.__file__).parent / "locales"


def keys(lang: str) -> set[str]:
    return set(json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8")))


def test_both_locales_have_the_same_keys() -> None:
    assert keys("en") == keys("ko")


def test_every_reason_code_has_a_message_in_both_languages() -> None:
    for code in CODES:
        assert f"finding.{code}" in keys("en")
        assert f"finding.{code}" in keys("ko")


def test_no_message_is_left_untranslated() -> None:
    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    ko = json.loads((LOCALES / "ko.json").read_text(encoding="utf-8"))
    same = [key for key in en if en[key] == ko[key]]
    assert same == []


def test_placeholders_match_between_languages() -> None:
    import re

    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    ko = json.loads((LOCALES / "ko.json").read_text(encoding="utf-8"))
    for key in en:
        assert set(re.findall(r"{(\w+)}", en[key])) == set(re.findall(r"{(\w+)}", ko[key])), key


def test_precedence_cli_over_env_over_locale() -> None:
    env = {"GENAI_PY_CODEMOD_LANG": "ko", "LANG": "en_US.UTF-8"}
    assert i18n.resolve_lang("en", env) == "en"  # --lang wins
    assert i18n.resolve_lang(None, env) == "ko"  # tool variable beats LANG
    assert i18n.resolve_lang(None, {"LC_ALL": "ko_KR.UTF-8", "LANG": "en_US.UTF-8"}) == "ko"
    assert i18n.resolve_lang(None, {"LC_MESSAGES": "ko_KR.UTF-8", "LANG": "en_US.UTF-8"}) == "ko"
    assert i18n.resolve_lang(None, {"LANG": "ko_KR.UTF-8"}) == "ko"


@pytest.mark.parametrize("value", ["fr_FR.UTF-8", "C", "POSIX", "", "ja_JP.UTF-8"])
def test_anything_that_is_not_korean_is_english(value: str) -> None:
    assert i18n.resolve_lang(None, {"LANG": value}) == "en"
    assert i18n.resolve_lang(None, {}) == "en"


def test_unknown_language_is_rejected() -> None:
    with pytest.raises(ValueError, match="choose one of"):
        i18n.load_messages("fr")


def test_translator_falls_back_to_the_key() -> None:
    assert i18n.Translator("en")("no.such.key") == "no.such.key"


def test_cli_output_changes_with_lang(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GENAI_PY_CODEMOD_LANG", raising=False)
    target = str(FIXTURES / "manual_handle_passed" / "before.py")
    main([target, "--lang", "en"])
    english = capsys.readouterr().out
    main([target, "--lang", "ko"])
    korean = capsys.readouterr().out
    assert "handle-escapes" in english and "handle-escapes" in korean  # codes never change
    assert "left unchanged" in english and "그대로 둡니다" in korean
    assert "spot(s) need a manual look" in english and "수동 확인 1곳" in korean


def test_environment_variable_selects_language(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENAI_PY_CODEMOD_LANG", "ko")
    main([str(FIXTURES / "manual_handle_passed" / "before.py")])
    assert "수동 확인" in capsys.readouterr().out
    main([str(FIXTURES / "manual_handle_passed" / "before.py"), "--lang", "en"])  # option overrides the variable
    assert "manual look" in capsys.readouterr().out


def test_help_is_translated(capsys: pytest.CaptureFixture[str]) -> None:
    for lang, needle in (("en", "Move Python code"), ("ko", "옮깁니다")):
        with pytest.raises(SystemExit):
            main(["--help", "--lang", lang])
        assert needle in capsys.readouterr().out


def test_json_report_keys_do_not_depend_on_language(capsys: pytest.CaptureFixture[str]) -> None:
    target = str(FIXTURES / "manual_handle_passed" / "before.py")
    main([target, "--report", "json", "--lang", "en"])
    en = json.loads(capsys.readouterr().out)
    main([target, "--report", "json", "--lang", "ko"])
    ko = json.loads(capsys.readouterr().out)
    strip = lambda d: {k: v for k, v in d["files"][0]["findings"][0].items() if k != "message"}  # noqa: E731
    assert strip(en) == strip(ko)
    assert en["files"][0]["findings"][0]["message"] != ko["files"][0]["findings"][0]["message"]


@pytest.mark.parametrize("argv", [["--help"], ["verify", "--help"]])
def test_korean_help_has_no_english_argparse_text(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        main([*argv, "--lang", "ko"])
    assert stop.value.code == 0
    out = capsys.readouterr().out
    for english in ("usage:", "positional arguments", "options:", "show this help message"):
        assert english not in out
    assert "사용법:" in out and "위치 인자" in out


def test_korean_usage_errors_are_korean(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        main(["--lang", "ko"])
    assert stop.value.code == 2
    err = capsys.readouterr().err
    assert "오류" in err and "PATH" in err and "arguments are required" not in err
    with pytest.raises(SystemExit):
        main(["x", "--report", "foo", "--lang", "ko"])
    assert "잘못된 값" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["x", "--lang", "en"] + ["--report", "foo"])
    assert "invalid choice" in capsys.readouterr().err  # English stays English


# --- Every user-visible sentence comes from the catalog ---------------------------------------------------------
# A sentence written straight into the code would bypass --lang. The scan below finds every string literal in the
# package that contains an English phrase (two words or more) and fails unless it is listed here with the reason it
# never reaches the user as a sentence of this tool. New UI text has to go to locales/*.json instead.

PACKAGE = Path(i18n.__file__).parent
PHRASE = re.compile(r"[A-Za-z]{2,}\s+[A-Za-z]{2,}")
ALLOWED_LITERALS: dict[tuple[str, str], str] = {
    ("cli.py", "genai-py-codemod verify"): "program name shown in usage lines",
    ("cli.py", "the following arguments are required: (.*)"): "pattern that recognizes argparse's English text",
    ("cli.py", "unrecognized arguments: (.*)"): "pattern that recognizes argparse's English text",
    ("cli.py", "argument (.+?): invalid choice: (.+?) \\(choose from (.*)\\)"): "pattern for argparse's text",
    ("cli.py", "argument (.+?): expected one argument"): "pattern that recognizes argparse's English text",
    ("cli.py", "argument (.+?): ignored explicit argument (.*)"): "pattern that recognizes argparse's English text",
    ("i18n.py", "unsupported language "): "library ValueError for a programmer mistake; --lang has fixed choices",
    ("i18n.py", "; choose one of: "): "same library ValueError",
    ("migrate.py", "api_version must be one of "): "library ValueError; --api-version has fixed choices",
    ("verify/runner.py", "mock response"): "fake model text given to the checked script, never printed",
    ("verify/runner.py", "network access is blocked by genai-py-codemod verify"): (
        "raised inside the checked script; the CLI shows verify.error.network-blocked instead"
    ),
}


def _docstring_ids(tree: ast.AST) -> set[int]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                found.add(id(first.value))
    return found


def _english_literals() -> list[tuple[str, str]]:
    found = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = _docstring_ids(tree)
        for node in ast.walk(tree):  # f-string pieces are Constant nodes inside JoinedStr, so they are seen too
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                if PHRASE.search(node.value):
                    found.append((path.relative_to(PACKAGE).as_posix(), node.value))
    return found


def test_no_english_sentence_outside_the_catalog() -> None:
    unexpected = [item for item in _english_literals() if item not in ALLOWED_LITERALS]
    assert unexpected == [], "move these texts to locales/en.json + ko.json and use the translator"


def test_allow_list_has_no_stale_entries() -> None:
    assert set(ALLOWED_LITERALS) <= set(_english_literals())


def _catalog_fragments() -> list[str]:
    """Fixed English pieces of every catalog message (the text between placeholders), two words or more."""
    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    pieces = set()
    for template in en.values():
        for piece in re.split(r"{\w+}|\n", template):
            piece = piece.strip(" :;,.()")
            if PHRASE.search(piece):
                pieces.add(piece)
    return sorted(pieces)


ENGLISH_RUN = re.compile(r"\b[a-z]{2,}(?: [a-z]{2,}){2,}\b")


def _tool_lines(text: str) -> list[str]:
    """Lines written by this tool; traceback lines quoted from the checked script are Python's, not ours."""
    return [
        line
        for line in text.splitlines()
        if line.strip() and not line.startswith(" ") and not re.match(r"^\w+(Error|Exception|Exit)\b", line)
    ]


def assert_no_english(text: str) -> None:
    leaked = [piece for piece in _catalog_fragments() if piece in text]
    assert leaked == [], f"English catalog text in Korean output: {leaked}\n{text}"
    for line in _tool_lines(text):
        assert not ENGLISH_RUN.search(line), f"English words in Korean output: {line!r}"


def _verify_case(name: str, tmp_path: Path) -> tuple[list[str], str]:
    """Arguments for one verify failure and the catalog key that must explain it."""
    script = {
        "timeout": "import time\ntime.sleep(30)\n",
        "script-exit": "raise SystemExit('boom')\n",
        "script-failed": "raise RuntimeError('boom')\n",
        "sdk-missing": "import module_that_does_not_exist_xyz\n",
        "network-blocked": "import socket\nsocket.create_connection(('example.com', 80))\n",
    }
    good = tmp_path / "good.py"
    good.write_text("x = 1\n")
    if name == "missing-file":
        return [str(tmp_path / "nope.py"), str(good)], name
    if name == "interpreter-not-found":
        return [str(good), str(good), "--old-python", str(tmp_path / "no-python")], name
    target = tmp_path / f"{name}.py"
    target.write_text(script[name])
    extra = ["--timeout", "1"] if name == "timeout" else []
    return [str(target), str(good), *extra], name


VERIFY_FAILURES = [
    "missing-file",
    "interpreter-not-found",
    "timeout",
    "script-exit",
    "script-failed",
    "sdk-missing",
    "network-blocked",
]


def test_every_verify_failure_code_is_tested_and_in_the_catalog() -> None:
    from genai_py_codemod.verify import ERROR_CODES

    tested = set(VERIFY_FAILURES) | {"no-result"}  # no-result needs a broken interpreter; key checked here only
    assert tested == set(ERROR_CODES)
    for code in ERROR_CODES:
        assert f"verify.error.{code}" in keys("en") and f"verify.error.{code}" in keys("ko")


@pytest.mark.parametrize("name", VERIFY_FAILURES)
def test_verify_failures_follow_lang(name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args, key = _verify_case(name, tmp_path)
    en_template = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))[f"verify.error.{key}"]
    ko_template = json.loads((LOCALES / "ko.json").read_text(encoding="utf-8"))[f"verify.error.{key}"]
    fixed = lambda template: max(re.split(r"{\w+}", template), key=len).strip()  # noqa: E731

    assert main(["verify", *args, "--lang", "ko"]) == 2
    korean = capsys.readouterr().err
    assert korean.startswith("검증할 수 없음: ")
    assert fixed(ko_template).split("\n")[0] in korean
    assert_no_english(korean)

    assert main(["verify", *args, "--lang", "en"]) == 2
    english = capsys.readouterr().err
    assert english.startswith("cannot verify: ") and fixed(en_template).split("\n")[0] in english

    assert main(["verify", *args, "--lang", "ko", "--json"]) == 2
    data = json.loads(capsys.readouterr().out)
    assert data["error"] == key  # language-independent code
    assert_no_english(data["message"])


def test_verify_diff_and_warning_lines_follow_lang(capsys: pytest.CaptureFixture[str]) -> None:
    from conftest import EXAMPLES

    pair = [str(EXAMPLES / "hand-migrated-bug" / "before.py"), str(EXAMPLES / "hand-migrated-bug" / "after.py")]
    assert main(["verify", *pair, "--lang", "ko"]) == 1
    korean = capsys.readouterr().out
    assert "(없음)" in korean and "경고: API 버전 v1beta -> v1" in korean
    assert "body.generationConfig.temperature" in korean  # request paths are data and stay as they are
    assert_no_english(korean)
    assert main(["verify", *pair, "--lang", "en"]) == 1
    english = capsys.readouterr().out
    assert "(missing)" in english and "warning: API version v1beta -> v1" in english

    folder = FIXTURES / "basic_generate"
    strict = [str(folder / "before.py"), str(folder / "expected.py"), "--strict-version"]
    assert main(["verify", *strict, "--lang", "ko"]) == 1
    korean = capsys.readouterr().out
    assert "API 버전 v1beta -> v1 (--strict-version: 같아야 함)" in korean
    assert_no_english(korean)
    assert main(["verify", *strict, "--lang", "ko", "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["warnings"] == ["API 버전 v1beta -> v1"]
    assert data["version_changes"] == [{"before": "v1beta", "after": "v1"}]


@pytest.mark.parametrize("kind", ["count", "method", "model", "version"])
def test_every_diff_kind_renders_in_both_languages(kind: str) -> None:
    from genai_py_codemod.verify.compare import MISSING, Diff

    diff = Diff(1, "generateContent", kind, "a" if kind != "count" else 1, MISSING if kind != "count" else 2, kind)
    korean = diff.render(i18n.Translator("ko"))
    english = diff.render(i18n.Translator("en"))
    assert korean != english
    assert_no_english(korean)
    assert diff.render() == english  # the library default is English


def test_korean_argument_errors_are_korean(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    cases = [
        (["verify", "a.py", "b.py", "--timeout", "abc", "--lang", "ko"], "잘못된 값"),
        (["x", "--write=yes", "--lang", "ko"], "값을 받지 않는"),
        (["x", "--lang"], "값이 하나 필요"),  # --lang without a value: language comes from the variable
    ]
    monkeypatch.setenv("GENAI_PY_CODEMOD_LANG", "ko")
    for argv, needle in cases:
        with pytest.raises(SystemExit) as stop:
            main(argv)
        assert stop.value.code == 2
        err = capsys.readouterr().err
        assert needle in err, err
        assert_no_english(err)


def test_korean_migrate_errors_are_korean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    broken = tmp_path / "broken.py"
    broken.write_text("import google.generativeai as genai\ndef (:\n")
    empty = tmp_path / "empty"
    empty.mkdir()
    for argv in (
        [str(broken)],
        [str(tmp_path / "missing.py")],
        [str(empty)],
        [str(broken), "--write", "--check"],
    ):
        assert main([*argv, "--lang", "ko"]) == 2
        captured = capsys.readouterr()
        text = captured.err + captured.out
        assert text.strip()
        assert_no_english(text)
