"""AC-2: Developer API fixtures convert to exactly expected.py (byte for byte) and a second run changes nothing."""

from __future__ import annotations

import pytest
from conftest import fixture_names, read

from genai_py_codemod import migrate_source

NAMES = fixture_names(exclude=("vertex_",))


def test_enough_fixtures() -> None:
    assert len(NAMES) >= 30


@pytest.mark.parametrize("name", NAMES)
def test_golden(name: str) -> None:
    before = read(name, "before.py")
    result = migrate_source(before, path=f"{name}/before.py")
    assert result.code == read(name, "expected.py")


@pytest.mark.parametrize("name", NAMES)
def test_second_run_changes_nothing(name: str) -> None:
    expected = read(name, "expected.py")
    again = migrate_source(expected, path=f"{name}/expected.py")
    assert not again.changed
    assert again.code == expected


def test_comments_blank_lines_and_layout_survive() -> None:
    out = read("generation_config_dict", "expected.py")
    assert "# Low temperature keeps the answers stable.\n" in out
    assert "temperature=0.2,  # stable\n" in out  # trailing comment moved with its key
    assert "model_config = types.GenerateContentConfig(\n    temperature=0.2," in out  # one argument per line kept
    assert " = " not in out.split("GenerateContentConfig(")[1].split(")")[0]  # no spaces around '=' in keyword args


def test_single_quotes_are_kept() -> None:
    out = read("single_quotes_trailing_comma", "expected.py")
    assert "os.environ['GOOGLE_API_KEY']" in out
    assert "system_instruction='Use single quotes.'" in out


def test_alias_imports_resolve() -> None:
    out = read("alias_imports", "expected.py")
    assert "client = genai.Client(" in out
    assert "generativeai" not in out
