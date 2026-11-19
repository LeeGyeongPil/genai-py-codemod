"""AC-9: --api-version auto | keep | none."""

from __future__ import annotations

import pytest
from conftest import read

from genai_py_codemod import migrate_source

PIN = 'http_options=types.HttpOptions(api_version="v1beta")'


def run(name: str, mode: str) -> str:
    return migrate_source(read(name, "before.py"), api_version=mode).code  # type: ignore[arg-type]


def test_auto_pins_only_for_latest_alias() -> None:
    assert PIN in run("latest_alias", "auto")
    assert PIN not in run("basic_generate", "auto")


@pytest.mark.parametrize("model", ["gemini-flash-latest", "gemini-2.5-flash-preview-05-20", "gemini-2.0-flash-exp"])
def test_auto_detects_beta_only_model_names(model: str) -> None:
    source = (
        "import google.generativeai as genai\n"
        'genai.configure(api_key="k")\n'
        f'm = genai.GenerativeModel("{model}")\n'
        'print(m.generate_content("x"))\n'
    )
    assert PIN in migrate_source(source).code


def test_keep_always_pins() -> None:
    assert PIN in run("basic_generate", "keep")
    assert PIN in run("latest_alias", "keep")


def test_none_never_pins() -> None:
    assert PIN not in run("latest_alias", "none")
    assert PIN not in run("basic_generate", "none")


def test_pin_is_added_to_a_client_created_without_configure() -> None:
    out = run("no_configure", "keep")
    assert "client = genai.Client(http_options=types.HttpOptions(" in out
    assert "from google.genai import types" in out


def test_vertex_keep_pins_the_old_default_version() -> None:
    out = migrate_source(read("vertex_basic", "before.py"), api_version="keep").code
    assert 'api_version="v1"' in out
    assert "api_version" not in migrate_source(read("vertex_basic", "before.py"), api_version="auto").code


def test_invalid_mode_is_rejected_with_a_fix() -> None:
    with pytest.raises(ValueError, match="auto, keep, none"):
        migrate_source("x = 1\n", api_version="v1")  # type: ignore[arg-type]
