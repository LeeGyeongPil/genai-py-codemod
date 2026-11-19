"""AC-4: spots that cannot be followed are reported with line and reason, and the file stays untouched."""

from __future__ import annotations

import json

import pytest
from conftest import fixture_names, read

from genai_py_codemod import migrate_source

NAMES = fixture_names(prefix="manual_")


def test_every_reason_code_has_a_fixture() -> None:
    covered = set()
    for name in NAMES:
        covered.update(item["code"] for item in json.loads(read(name, "findings.json")))
    expected = {
        "handle-escapes",
        "handle-reassigned",
        "handle-untracked",
        "call-kwargs",
        "call-config-merge",
        "callable-tools-afc",
        "count-tokens-semantics",
        "async-chat",
        "files-api",
        "caches-api",
        "configure-scope",
        "configure-args",
        "unsupported-api",
        "history-format",
    }
    assert expected <= covered


@pytest.mark.parametrize("name", NAMES)
def test_manual_points_are_reported_and_code_is_unchanged(name: str) -> None:
    before = read(name, "before.py")
    result = migrate_source(before, path=f"{name}/before.py")
    want = json.loads(read(name, "findings.json"))
    got = [{"line": f.line, "code": f.code} for f in result.findings if f.severity == "manual"]
    assert got == want
    assert not result.changed
    assert result.code == before == read(name, "expected.py")
    lines = before.splitlines()
    for item in want:  # the reported line really is the original text
        assert lines[item["line"] - 1] in result.code


def test_info_findings_do_not_block_conversion() -> None:
    result = migrate_source(read("dynamic_model_name", "before.py"))
    assert result.changed
    assert [(f.code, f.severity) for f in result.findings] == [("dynamic-model", "info")]


def test_one_bad_spot_keeps_the_whole_file() -> None:
    source = (
        "import google.generativeai as genai\n"
        'genai.configure(api_key="k")\n'
        'good = genai.GenerativeModel("gemini-2.5-flash")\n'
        'bad = genai.GenerativeModel("gemini-2.5-flash")\n'
        "def use(m):\n    return m\n"
        'print(good.generate_content("x"), use(bad))\n'
    )
    result = migrate_source(source)
    assert not result.changed and result.code == source
    assert [f.code for f in result.findings] == ["handle-escapes"]
